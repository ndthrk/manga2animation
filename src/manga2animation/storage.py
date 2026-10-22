"""Lưu project và bản chỉnh sửa riêng, không ghi đè kết quả trích xuất."""
import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from PIL import Image, ImageOps
import yaml
from .settings import ROOT, read_config, validate_config

_io_lock = threading.RLock()


def replace_file(temporary, path):
    # Windows có thể khóa file trong lúc trình duyệt đọc hoặc antivirus quét.
    for attempt in range(40):
        try:
            os.replace(temporary, path)
            return
        except PermissionError:
            if attempt == 39:
                raise
            time.sleep(.025)


def now():
    return datetime.now(timezone.utc).isoformat()


def uid():
    return uuid4().hex


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uid() + '.tmp')
    with _io_lock:
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
        replace_file(temporary, path)


def read_json(path):
    with _io_lock:
        return json.loads(Path(path).read_text(encoding='utf-8'))


def safe_path(root, relative):
    root = Path(root).resolve()
    target = (root / relative).resolve()
    if not target.is_relative_to(root):
        raise ValueError('Đường dẫn nằm ngoài project.')
    return target


class ProjectStore:
    def __init__(self, root=None):
        self.root = Path(root or ROOT / 'projects').resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()

    def folder(self, project_id):
        if not isinstance(project_id, str) or len(project_id) != 32 or any(c not in '0123456789abcdef' for c in project_id):
            raise ValueError('ID không hợp lệ.')
        return safe_path(self.root, project_id)

    def get(self, project_id):
        return read_json(self.folder(project_id) / 'project.json')

    def list(self):
        return [read_json(p) for p in sorted(self.root.glob('*/project.json'))]

    def create(self, name):
        project = {'id': uid(), 'name': name.strip() or 'Dự án mới', 'created_at': now(),
                   'pages': [], 'characters': [], 'global_prompt': '', 'revision': 0}
        folder = self.folder(project['id'])
        folder.mkdir()
        (folder / 'config.yaml').write_text(yaml.safe_dump(read_config(), allow_unicode=True, sort_keys=False), encoding='utf-8')
        prompt = ROOT / 'configs/global_prompt.txt'
        if prompt.exists():
            project['global_prompt'] = prompt.read_text(encoding='utf-8')
        write_json(folder / 'project.json', project)
        return project

    def update(self, project_id, changes):
        with self.lock:
            project = self.get(project_id)
            if changes.get('revision', project['revision']) != project['revision']:
                raise ValueError('Project đã thay đổi; hãy tải lại trước khi lưu.')
            for key in ('name', 'global_prompt', 'characters', 'pages', 'unknown_character'):
                if key in changes:
                    project[key] = changes[key]
            for page in project['pages']:
                safe_path(self.folder(project_id), page['image'])
                if 'layout' in page and page['layout'] is not None:
                    from .services.page_layout import validate_layout
                    with Image.open(safe_path(self.folder(project_id), page['image'])) as image:
                        page['layout'] = validate_layout(page['layout'], image.size)
            ids = [c['id'] for c in project['characters']]
            if len(ids) != len(set(ids)):
                raise ValueError('ID nhân vật phải duy nhất.')
            project['revision'] += 1
            write_json(self.folder(project_id) / 'project.json', project)
            return project

    def config(self, project_id, text=None):
        path = self.folder(project_id) / 'config.yaml'
        if text is not None:
            validate_config(yaml.safe_load(text))
            temporary = path.with_suffix('.tmp')
            temporary.write_text(text, encoding='utf-8')
            replace_file(temporary, path)
        # Bổ sung mặc định khi mở project cũ, không ghi lại snapshot đã trích xuất.
        raw = path.read_text(encoding='utf-8')
        normalized = validate_config(yaml.safe_load(raw))
        return yaml.safe_dump(normalized, allow_unicode=True, sort_keys=False)

    def upload_audio(self, project_id, filename, data):
        import io
        import soundfile as sf
        if len(data) > 50*1024*1024:
            raise ValueError('Âm thanh mẫu tối đa 50 MB.')
        try:
            samples, rate = sf.read(io.BytesIO(data), dtype='float32', always_2d=True)
        except Exception as exc:
            raise ValueError('Không đọc được âm thanh. Hãy dùng WAV, FLAC hoặc OGG.') from exc
        if not len(samples) or len(samples)/rate > 180:
            raise ValueError('Âm thanh mẫu cần dài hơn 0 và không quá 180 giây.')
        relative = f'voice_references/{uid()}.wav'
        path = safe_path(self.folder(project_id), relative)
        path.parent.mkdir(exist_ok=True)
        sf.write(path, samples.mean(axis=1), rate)
        return {'path': relative, 'name': Path(filename).name, 'duration': len(samples)/rate, 'sample_rate': rate}

    def assert_idle(self, folder):
        from .services.gpu import process_alive
        folder = Path(folder)
        paths = list(folder.glob('extracts/*/status.json'))+list(folder.glob('tasks/*/status.json'))
        paths += list(folder.glob('videos/*/status.json'))
        paths += list(folder.glob('extracts/*/proposals/*.json'))+list(folder.glob('proposals/*.json'))
        if (folder/'status.json').is_file():
            paths.append(folder/'status.json')
        for path in paths:
            status = read_json(path)
            if status.get('state') in ('queued', 'running', 'cancelling') and process_alive(status.get('pid')):
                raise ValueError('Còn tác vụ đang chạy. Hãy dừng và đợi hoàn tất trước khi xóa.')

    def delete_project(self, project_id):
        with self.lock:
            source = self.folder(project_id)
            self.get(project_id)
            self.assert_idle(source)
            destination = safe_path(self.root, '.trash/'+project_id+'_'+uid())
            destination.parent.mkdir(exist_ok=True)
            replace_file(source, destination)
            return {'deleted': True, 'trash': str(destination.relative_to(self.root))}

    def delete_run(self, project_id, run_id):
        with self.lock:
            source = self.run_folder(project_id, run_id)
            self.assert_idle(source)
            for path in (self.folder(project_id)/'tasks').glob('*/status.json'):
                task = read_json(path)
                if task.get('run_id') == run_id and task.get('state') in ('queued', 'running', 'cancelling'):
                    raise ValueError('Lần Extract còn tác vụ dịch/âm thanh đang chạy.')
            destination = safe_path(self.folder(project_id), '.trash/'+run_id+'_'+uid())
            destination.parent.mkdir(exist_ok=True)
            replace_file(source, destination)
            return {'deleted': True, 'trash': str(destination.relative_to(self.folder(project_id)))}

    def upload(self, project_id, filename, data, reference=False):
        with self.lock:
            folder = self.folder(project_id)
            relative = f"{'references' if reference else 'sources'}/{uid()}.png"
            path = safe_path(folder, relative)
            path.parent.mkdir(exist_ok=True)
            import io
            with Image.open(io.BytesIO(data)) as image:
                ImageOps.exif_transpose(image).convert('RGB').save(path)
            item = {'id': uid(), 'name': Path(filename).name, 'image': relative}
            if not reference:
                project = self.get(project_id)
                project['pages'].append(item)
                self.update(project_id, project)
            return item

    def extraction_plan(self, project_id, base_run_id=None, force=False, config_text=None):
        from .services.incremental import make_plan
        with self.lock:
            project = self.get(project_id)
            cfg = validate_config(yaml.safe_load(config_text or self.config(project_id)))
            return make_plan(self.folder(project_id), project, cfg, base_run_id, force)

    def new_run(self, project_id, base_run_id=None, force=False):
        with self.lock:
            project = self.get(project_id)
            if not project['pages']:
                raise ValueError('Cần tải ít nhất một ảnh trang truyện.')
            plan = self.extraction_plan(project_id, base_run_id, force)
            folder = self.folder(project_id) / 'extracts' / uid()
            folder.mkdir(parents=True)
            config = validate_config(yaml.safe_load(self.config(project_id)))
            (folder / 'config.yaml').write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding='utf-8')
            # Chụp lại cả ảnh để lần chạy cũ độc lập với thay đổi sau này.
            import shutil
            for item in project['pages'] + project['characters']:
                voice = item.get('voice', {})
                assets = [item.get('image'), voice.get('reference_audio'), voice.get('prompt'), voice.get('preview')]
                for asset in filter(None, assets):
                    dest = safe_path(folder, asset)
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(safe_path(self.folder(project_id), asset), dest)
            write_json(folder / 'snapshot.json', project)
            from .services.incremental import snapshot_reuse
            snapshot_reuse(self.folder(project_id), folder, plan)
            write_json(folder / 'status.json', {'id': folder.name, 'state': 'queued', 'stage': 'queued',
                                               'page': 0, 'total': len(project['pages']), 'created_at': now(), 'pid': os.getpid(),
                                               'mode': plan['mode'], 'base_run_id': plan['base_run_id'],
                                               'reused_pages': plan['reused_pages'], 'processing_pages': plan['processing_pages']})
            return folder

    def run_folder(self, project_id, run_id):
        if not isinstance(run_id, str) or len(run_id) != 32 or any(c not in '0123456789abcdef' for c in run_id):
            raise ValueError('ID lần trích xuất không hợp lệ.')
        return self.folder(project_id) / 'extracts' / run_id

    def edits(self, folder, changes=None):
        with self.lock:
            path = Path(folder) / 'edits.json'
            current = read_json(path)
            if changes is None:
                return current
            if changes.get('revision') != current['revision']:
                raise ValueError('Bản chỉnh sửa đã thay đổi; hãy tải lại.')
            manifest = read_json(Path(folder) / 'manifest.json')
            valid = {p['id'] for page in manifest['pages'] for p in page['panels']}
            if set(changes['order']) != valid or len(changes['order']) != len(valid):
                raise ValueError('Timeline phải giữ đủ ID panel, dùng hidden để ẩn.')
            if set(changes['panels']) != valid:
                raise ValueError('Thiếu dữ liệu chỉnh sửa panel.')
            batch_ids = {b['id'] for b in changes['batches']}
            for panel in changes['panels'].values():
                if panel['duration'] <= 0 or panel['batch_id'] not in batch_ids:
                    raise ValueError('Thời lượng hoặc batch không hợp lệ.')
            from .services.timing import update_durations
            config = validate_config(yaml.safe_load(self.config(Path(folder).parents[1].name)))
            project = self.get(Path(folder).parents[1].name)
            update_durations(changes, config['timing'], project['characters']+([project['unknown_character']] if project.get('unknown_character') else []))
            changes['revision'] = current['revision'] + 1
            changes['saved_at'] = now()
            write_json(path, changes)
            return changes
