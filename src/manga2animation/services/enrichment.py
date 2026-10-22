"""Tác vụ dịch/clone/TTS chạy sau Extract và trả kết quả riêng để ghép an toàn."""
from copy import deepcopy
from pathlib import Path
import hashlib
import json
import os
import threading
import yaml
from ..settings import validate_config
from ..storage import read_json, write_json, now, uid, safe_path
from .timing import dialogue_text
from .translations import translation_of, set_translation
from ..languages import canonical_language
from .gpu import gpu_slot, process_alive
from .cancellation import check_cancel, ExtractionCancelled


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class EnrichmentService:
    def __init__(self, store, executor, translation_factory=None, audio_provider=None):
        self.store, self.executor = store, executor
        if translation_factory is None:
            from ..translation.google import GoogleTranslationProvider
            translation_factory = GoogleTranslationProvider
        if audio_provider is None:
            from ..audio.omnivoice import OmniVoiceProvider
            audio_provider = OmniVoiceProvider()
        self.translation_factory, self.audio_provider = translation_factory, audio_provider
        for path in store.root.glob('*/tasks/*/status.json'):
            task = read_json(path)
            if task['state'] in ('queued', 'running') and not process_alive(task.get('pid')):
                task.update(state='interrupted', error='Dịch vụ đã dừng khi tác vụ chưa hoàn tất.')
                write_json(path, task)

    def list(self, pid):
        return sorted([read_json(p) for p in (self.store.folder(pid)/'tasks').glob('*/status.json')],
                      key=lambda t: t['created_at'], reverse=True)

    def task_folder(self, pid, task_id):
        if not isinstance(task_id, str) or len(task_id) != 32 or any(c not in '0123456789abcdef' for c in task_id):
            raise ValueError('ID tác vụ không hợp lệ.')
        return self.store.folder(pid)/'tasks'/task_id

    def submit(self, pid, operation, body):
        with self.store.lock:
            project = self.store.get(pid)
            cfg = validate_config(yaml.safe_load(self.store.config(pid)))
            if operation not in ('translate', 'audio', 'clone', 'preview', 'llm_pull'):
                raise ValueError('Loại tác vụ không hợp lệ.')
            run_id = body.get('run_id')
            if operation in ('translate', 'audio') and not run_id:
                raise ValueError('Cần chọn một lần Extract để xử lý hội thoại.')
            task_id = uid()
            folder = self.task_folder(pid, task_id)
            folder.mkdir(parents=True)
            task = {'id': task_id, 'project_id': pid, 'run_id': run_id, 'operation': operation,
                    'state': 'queued', 'created_at': now(), 'pid': os.getpid(), 'completed': 0, 'total': 0}
            request = {'body': deepcopy(body), 'project': project, 'config': cfg}
            if operation in ('translate', 'audio'):
                edits = self.store.edits(self.store.run_folder(pid, run_id))
                selected_panels = body.get('panel_ids') or [p for p in edits['order'] if not edits['panels'][p]['hidden']]
                selected_dialogues = body.get('dialogue_ids')
                items = []
                for panel_id in selected_panels:
                    if panel_id not in edits['panels']:
                        raise ValueError('Không tìm thấy panel cần xử lý.')
                    panel = edits['panels'][panel_id]
                    section = 'translation' if operation == 'translate' else 'audio'
                    settings = {**cfg[section], **panel.get(section+'_settings', {})}
                    for dialogue in panel['dialogues']:
                        if selected_dialogues and dialogue['id'] not in selected_dialogues:
                            continue
                        text = dialogue['text'] if operation == 'translate' else dialogue_text(dialogue, settings['text_source'], settings.get('translation_language'))
                        if text.strip():
                            targets = body.get('targets') or settings.get('targets') or [settings['target']] if operation == 'translate' else [None]
                            if not isinstance(targets, list) or len(targets) > 20 or any(not isinstance(t, str) or not t.strip() for t in targets if t is not None):
                                raise ValueError('Danh sách ngôn ngữ đích không hợp lệ (tối đa 20).')
                            for target in dict.fromkeys(canonical_language(t) if t else t for t in targets):
                                options = {**settings, **({'target': target} if target else {})}
                                items.append({'panel_id': panel_id, 'dialogue': deepcopy(dialogue), 'input_text': text, 'settings': options,
                                              'panel_audio_settings': panel.get('audio_settings', {})})
                if not items:
                    raise ValueError('Không có lời thoại phù hợp để xử lý. Nếu chọn bản dịch, hãy dịch trước.')
                request['items'] = items
                task['total'] = len(items)
            elif operation == 'llm_pull':
                options = {**cfg['translation']['ollama'], **body.get('settings', {})}
                request['settings'] = options
                task['model'] = options.get('model', '')
                task['total'] = 1
            else:
                character = (project.get('unknown_character') or {'id': 'unknown', 'name': 'Unknown'}) if body.get('character_id') == 'unknown' else next((c for c in project['characters'] if c['id'] == body.get('character_id')), None)
                if not character:
                    raise ValueError('Không tìm thấy nhân vật.')
                request['character'] = character
                request['settings'] = {**cfg['audio'], **character.get('audio_settings', {})}
                task['total'] = 1
            write_json(folder/'request.json', request)
            write_json(folder/'status.json', task)
            self.executor.submit(self._work, folder)
            return task

    def _work(self, folder):
        task = read_json(folder/'status.json')
        request = read_json(folder/'request.json')
        try:
            check_cancel(folder)
            task['state'] = 'running'
            write_json(folder/'status.json', task)
            if task['operation'] == 'translate':
                if any(i['settings']['provider']=='ollama' for i in request['items']):
                    with gpu_slot():
                        self._translate(folder, task, request)
                else:
                    self._translate(folder, task, request)
            elif task['operation'] == 'llm_pull':
                from ..translation.llm import pull_model
                def progress(item):
                    task.update(download_status=item.get('status',''), download_total=item.get('total',0), download_completed=item.get('completed',0))
                    write_json(folder/'status.json',task)
                pull_model(request['settings'],progress,cancelled=lambda:check_cancel(folder))
                task['completed'] = 1
            else:
                with gpu_slot():
                    check_cancel(folder)
                    self._audio(folder, task, request)
            check_cancel(folder)
            task.update(state='completed', updated_at=now())
        except ExtractionCancelled as exc:
            task.update(state='cancelled', error=str(exc))
        except Exception as exc:
            task.update(state='failed', error=str(exc))
        finally:
            write_json(folder/'status.json', task)

    def apply(self, pid, task_id, revisions):
        """Chỉ ghép kết quả nếu câu/giọng/bản dịch chưa đổi trong thời gian chạy."""
        with self.store.lock:
            path = self.task_folder(pid, task_id)/'status.json'
            task = read_json(path)
            if task['state'] != 'completed':
                raise ValueError('Tác vụ chưa hoàn tất.')
            if task.get('applied_at'):
                return {'task': task, 'project': self.store.get(pid),
                        'edits': self.store.edits(self.store.run_folder(pid, task['run_id'])) if task.get('run_id') else None}
            skipped = 0
            project = self.store.get(pid)
            edits = None
            if task['operation'] == 'clone':
                if revisions.get('project_revision') != project['revision']:
                    raise ValueError('Project đã thay đổi; lưu và thử áp dụng lại.')
                result = task['voice_result']
                character = project.setdefault('unknown_character', {'id': 'unknown', 'name': 'Unknown', 'color': '#a5a5b8'}) if result['character_id'] == 'unknown' else next((c for c in project['characters'] if c['id'] == result['character_id']), None)
                if character and character.get('voice', {}) == result['previous_voice']:
                    character['voice'] = result['voice']
                    project = self.store.update(pid, project)
                else:
                    skipped += 1
            elif task['operation'] in ('translate', 'audio'):
                folder = self.store.run_folder(pid, task['run_id'])
                edits = self.store.edits(folder)
                if revisions.get('revision') != edits['revision']:
                    raise ValueError('Bản chỉnh sửa đã thay đổi; lưu và thử áp dụng lại.')
                characters = {c['id']: c for c in project['characters']}
                for result in task.get('results', []):
                    panel = edits['panels'].get(result['panel_id'])
                    line = next((d for d in panel['dialogues'] if d['id'] == result['dialogue_id']), None) if panel else None
                    key = 'translation' if task['operation'] == 'translate' else 'audio'
                    source = 'original' if key == 'translation' else result['audio']['text_source']
                    unchanged = line is not None and dialogue_text(line, source, result.get('audio', {}).get('translation_language')) == result['input_text']
                    if unchanged and key == 'audio':
                        owner = characters.get(line['speaker_id']) or project.get('unknown_character', {})
                        unchanged = line['speaker_id'] == result['audio']['speaker_id'] and owner.get('voice', {}).get('prompt') == result['audio']['voice_id']
                    previous = translation_of(line, result[key]['target']) or None if key == 'translation' and line is not None else line.get(key) if line else None
                    if unchanged and previous == result.get('previous_'+key):
                        if key == 'translation':
                            set_translation(line, result[key])
                        else:
                            line[key] = result[key]
                    else:
                        skipped += 1
                edits = self.store.edits(folder, edits)
            task.update(applied_at=now(), skipped=skipped)
            write_json(path, task)
            return {'task': task, 'project': project, 'edits': edits}

    def _translate(self, folder, task, request):
        items = request['items']
        results, errors = [], []
        groups = {}
        for item in items:
            groups.setdefault(fingerprint(item['settings']), []).append(item)
        for group in groups.values():
            settings = group[0]['settings']
            provider_name = settings['provider']
            if provider_name == 'googletrans':
                provider = self.translation_factory(timeout_seconds=settings['timeout_seconds'],
                                                    request_interval=settings.get('request_interval', 1), retries=settings.get('retries', 2),
                                                    batch_requests=settings.get('batch_requests',True),
                                                    max_chars_per_request=settings.get('max_chars_per_request',4000))
            else:
                from ..translation.llm import LLMTranslationProvider
                options = settings[provider_name]
                provider = LLMTranslationProvider(provider_name,options,timeout_seconds=options['timeout_seconds'],
                                                    cancelled=lambda:check_cancel(folder))
            size = settings['batch_size']
            before_requests = task.get('translation_requests',0)
            before_input_tokens, before_output_tokens = task.get('input_tokens',0), task.get('output_tokens',0)
            before_cached = task.get('cached_sentences',0)
            from ..translation.batching import pack_items
            by_text = {}
            for item in group:
                by_text.setdefault(item['input_text'],[]).append(item)
            unique = [values[0] for values in by_text.values()]
            task['deduplicated_sentences'] = task.get('deduplicated_sentences',0)+len(group)-len(unique)
            for chunk in pack_items(unique,size,settings.get('max_chars_per_request',4000)):
                check_cancel(folder)
                try:
                    translated = provider.translate([i['input_text'] for i in chunk], source=settings['source'], target=settings['target'])
                    if len(translated) != len(chunk):
                        raise ValueError('Provider trả thiếu bản dịch.')
                    for representative, result in zip(chunk, translated):
                        if result.get('error'):
                            errors.extend({'panel_id': item['panel_id'], 'dialogue_id': item['dialogue']['id'], 'error': result['error']} for item in by_text[representative['input_text']])
                            continue
                        for item in by_text[representative['input_text']]:
                            results.append({'panel_id': item['panel_id'], 'dialogue_id': item['dialogue']['id'],
                                        'input_text': item['input_text'], 'translation': {**result, 'provider': provider_name,
                                        'target': settings['target'], 'input_text': item['input_text'], 'created_at': now()},
                                        'previous_translation': translation_of(item['dialogue'], settings['target']) or None})
                except ExtractionCancelled:
                    raise
                except Exception as exc:
                    errors.extend({'panel_id': i['panel_id'], 'dialogue_id': i['dialogue']['id'], 'error': str(exc)} for item in chunk for i in by_text[item['input_text']])
                task.update(completed=min(task['total'], task['completed']+sum(len(by_text[i['input_text']]) for i in chunk)), results=results, errors=errors)
                task['translation_requests'] = before_requests+getattr(provider,'request_count',0)
                task['input_tokens'] = before_input_tokens+getattr(provider,'input_tokens',0)
                task['output_tokens'] = before_output_tokens+getattr(provider,'output_tokens',0)
                task['cached_sentences'] = before_cached+getattr(provider,'cached_count',0)
                write_json(folder/'status.json', task)
        if errors and not results:
            raise RuntimeError(errors[0]['error'])

    def _audio(self, folder, task, request):
        project_folder = self.store.folder(task['project_id'])
        operation = task['operation']
        results, errors = [], []
        if operation in ('clone', 'preview'):
            character, settings = request['character'], request['settings']
            voice = character.get('voice', {})
            preview_text = request['body'].get('text', '').strip()
            if not preview_text:
                raise ValueError('Hãy nhập văn bản nghe thử.')
            output = project_folder/'voices'/character['id']/task['id']
            # ID nhân vật có thể nhập qua API; luôn kiểm tra đường dẫn sau khi ghép.
            output = safe_path(project_folder, output)
            output.mkdir(parents=True, exist_ok=True)
            if operation == 'clone':
                reference = safe_path(project_folder, voice.get('reference_audio', ''))
                if not reference.is_file():
                    raise ValueError('Cần tải âm thanh tham chiếu trước khi clone.')
                payload = {'operation': 'clone', 'reference_audio': str(reference),
                           'reference_text': voice.get('reference_text', ''), 'preview_text': preview_text,
                           'prompt_output': str(output/'prompt.pt'), 'preview_output': str(output/'preview.wav')}
            else:
                prompt = safe_path(project_folder, voice.get('prompt', ''))
                if not prompt.is_file():
                    raise ValueError('Nhân vật chưa có giọng đã clone.')
                payload = {'operation': 'generate', 'items': [{'id': 'preview', 'text': preview_text,
                           'prompt': str(prompt), 'output': str(output/'preview.wav')}]}
            result = self.audio_provider.run(folder, settings, payload, cancelled=lambda: check_cancel(folder))
            if operation == 'clone':
                task['voice_result'] = {'character_id': character['id'], 'previous_voice': voice,
                    'voice': {**voice, 'reference_text': result.get('reference_text', voice.get('reference_text', '')),
                              'reference_text_source': result.get('reference_text_source', 'manual'),
                              'prompt': str((output/'prompt.pt').relative_to(project_folder)).replace('\\','/'),
                              'preview': str((output/'preview.wav').relative_to(project_folder)).replace('\\','/'),
                              'preview_text': preview_text, 'duration': result['duration'], 'cloned_at': now()}}
            else:
                task['preview'] = str((output/'preview.wav').relative_to(project_folder)).replace('\\','/')
                task['preview_duration'] = result['clips'][0]['duration']
            task['completed'] = 1
            return
        characters = {c['id']: c for c in request['project']['characters']}
        groups = {}
        descriptors = {}
        for item in request['items']:
            check_cancel(folder)
            character = characters.get(item['dialogue']['speaker_id']) or request['project'].get('unknown_character', {})
            voice = character.get('voice', {}) if character else {}
            prompt = safe_path(project_folder, voice.get('prompt', ''))
            if not prompt.is_file():
                errors.append({'panel_id': item['panel_id'], 'dialogue_id': item['dialogue']['id'], 'error': 'Người nói chưa có giọng đã clone.'})
                task['completed'] += 1
                continue
            settings = {**item['settings'], **character.get('audio_settings', {}), **item.get('panel_audio_settings', {})}
            if request['body'].get('reuse_existing'):
                from .timing import valid_audio
                clip = item['dialogue'].get('audio', {})
                if (valid_audio(item['dialogue']) and clip.get('voice_id') == voice.get('prompt')
                        and clip.get('settings') == settings and safe_path(project_folder, clip['path']).is_file()):
                    task['completed'] += 1
                    task['reused_clips'] = task.get('reused_clips', 0)+1
                    continue
            key = fingerprint(settings)
            entry = groups.setdefault(key, {'settings': settings, 'items': []})
            item_id = uid()
            output = self.store.run_folder(task['project_id'], task['run_id'])/'audio'/task['id']/(item_id+'.wav')
            output.parent.mkdir(parents=True, exist_ok=True)
            entry['items'].append({'id': item_id, 'text': item['input_text'], 'prompt': str(prompt), 'output': str(output)})
            descriptors[item_id] = {**item, 'voice_id': voice['prompt'], 'output': output}
        for index, group in enumerate(groups.values()):
            check_cancel(folder)
            group_folder = folder/f'group_{index}'
            group_folder.mkdir()
            completed_before = task['completed']
            def progress(count):
                task['completed'] = completed_before + count
                write_json(folder/'status.json', task)
            try:
                result = self.audio_provider.run(group_folder, group['settings'], {'operation': 'generate', 'items': group['items']},
                                                 cancelled=lambda: check_cancel(folder), progress=progress)
                for clip in result['clips']:
                    item = descriptors[clip['id']]
                    results.append({'panel_id': item['panel_id'], 'dialogue_id': item['dialogue']['id'],
                                    'input_text': item['input_text'], 'audio': {
                                        'path': str(item['output'].relative_to(project_folder)).replace('\\','/'),
                                        'input_text': item['input_text'], 'speaker_id': item['dialogue']['speaker_id'],
                                        'text_source': group['settings']['text_source'], 'voice_id': item['voice_id'],
                                        'translation_language': group['settings'].get('translation_language'),
                                        'duration': clip['duration'], 'sample_rate': clip['sample_rate'],
                                        'settings': group['settings'], 'created_at': now()},
                                    'previous_audio': item['dialogue'].get('audio')})
            except ExtractionCancelled:
                raise
            except Exception as exc:
                for item in group['items']:
                    original = descriptors[item['id']]
                    errors.append({'panel_id': original['panel_id'], 'dialogue_id': original['dialogue']['id'], 'error': str(exc)})
            task.update(completed=completed_before+len(group['items']), results=results, errors=errors)
            write_json(folder/'status.json', task)
        task.update(results=results, errors=errors)
        if errors and not results:
            raise RuntimeError(errors[0]['error'])
