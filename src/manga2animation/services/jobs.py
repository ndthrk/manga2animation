"""Một worker duy nhất cho mọi extract/OCR để tránh nạp hai model GPU cùng lúc."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import yaml
from PIL import Image
from ..storage import read_json, write_json, now, uid
from .extraction import extract
from .models import ModelAdapters, release_models
from .gpu import gpu_serialized, process_alive
from ..settings import validate_config
from ..ocr import normalize_text
import os


class JobQueue:
    def __init__(self, store, adapters=None):
        self.store = store
        self.adapters = adapters or ModelAdapters()
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='manga-gpu')
        self.futures = {}
        from .enrichment import EnrichmentService
        self.enrichment = EnrichmentService(store, self.executor)
        for path in store.root.glob('*/extracts/*/status.json'):
            status = read_json(path)
            if status['state'] in ('queued', 'running', 'cancelling') and not process_alive(status.get('pid')):
                status.update(state='interrupted', error='Dịch vụ đã dừng trước khi hoàn tất.')
                write_json(path, status)
        for path in store.root.glob('*/extracts/*/proposals/*.json'):
            status = read_json(path)
            if status['state'] in ('queued', 'running') and not process_alive(status.get('pid')):
                status.update(state='failed', error='Dịch vụ đã dừng trước khi OCR hoàn tất.')
                write_json(path, status)

    def submit_extract(self, project_id, base_run_id=None, force=False):
        folder = self.store.new_run(project_id, base_run_id=base_run_id, force=force)
        # Luồng dùng lại toàn bộ có thể xong ngay; luôn trả queued để UI tải kết quả qua polling.
        submitted = read_json(folder / 'status.json')
        self.futures[folder.name] = self.executor.submit(self._extract, folder)
        return submitted

    def cancel_extract(self, folder):
        with self.store.lock:
            status = read_json(folder/'status.json')
            if status['state'] in ('queued', 'running', 'cancelling'):
                (folder/'cancel.requested').touch()
                future = self.futures.get(folder.name)
                cancelled = future.cancel() if future else False
                status.update(state='cancelled' if cancelled else 'cancelling',
                              stage='cancelled' if cancelled else 'cancelling', updated_at=now())
                write_json(folder/'status.json', status)
            return status

    def _extract(self, folder):
        try:
            extract(folder, self.adapters)
        except Exception:
            # Chi tiết lỗi đã được ghi vào status; không giữ traceback chứa model GPU.
            import logging
            logging.exception('Trích xuất thất bại: %s', folder)
        finally:
            if read_json(folder/'status.json').get('processing_pages', 1):
                release_models()

    def submit_ocr(self, folder, panel_id, engine, options=None):
        manifest = read_json(folder / 'manifest.json')
        match = [(page, p) for page in manifest['pages'] for p in page['panels'] if p['id'] == panel_id]
        if not match:
            raise ValueError('Không tìm thấy panel.')
        proposal = {'id': uid(), 'panel_id': panel_id, 'engine': engine, 'options': options or {},
                    'state': 'queued', 'created_at': now(), 'pid': os.getpid()}
        path = folder / 'proposals' / (proposal['id'] + '.json')
        write_json(path, proposal)
        self.executor.submit(self._ocr, folder, path, *match[0])
        return proposal

    @gpu_serialized
    def _ocr(self, folder, path, page, panel):
        proposal = read_json(path)
        model = processor = recognizer = None
        try:
            proposal['state'] = 'running'
            write_json(path, proposal)
            cfg = validate_config(yaml.safe_load(self.store.config(folder.parents[1].name)))
            engine = proposal['engine']
            if engine in ('paddleocr','tesseract') and proposal['options'].get('language'):
                cfg['ocr'][engine]['language'] = proposal['options']['language']
            if engine.startswith('magi_'):
                model, processor = self.adapters.magi(cfg['magi'], engine.replace('magi_', ''))
            recognizer = self.adapters.recognizer(engine, cfg, model, processor)
            dialogues = []
            with Image.open(folder / page['upscaled_image']) as image:
                for text in panel['texts']:
                    result = recognizer.recognize(image.crop(text['bbox_padded']['upscaled']))
                    dialogues.append({'id': text['id'], 'text': normalize_text(result['content']),
                                      'speaker_id': text['speaker_id'], 'ocr': result})
                if not panel['texts']:
                    result = recognizer.recognize(image.crop(panel['bbox']))
                    dialogues.append({'id': uid(), 'text': normalize_text(result['content']), 'speaker_id': 'unknown', 'ocr': result})
            proposal.update(state='completed', dialogues=dialogues)
        except Exception as exc:
            proposal.update(state='failed', error=str(exc))
        finally:
            del recognizer, model, processor
            release_models()
            write_json(path, proposal)

    def close(self):
        self.executor.shutdown(wait=True)
        close = getattr(self.enrichment.audio_provider, 'close', None)
        if close:
            close()
