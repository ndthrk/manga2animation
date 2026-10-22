"""API local; giao diện chỉ giao tiếp qua HTTP, không import thư viện model."""
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from typing import Literal
from .storage import ProjectStore, read_json, write_json, safe_path, now
from .settings import ROOT, ENGINES
from .services.jobs import JobQueue
import yaml
from PIL import UnidentifiedImageError


class Name(BaseModel):
    name: str = 'Dự án mới'


class ConfigBody(BaseModel):
    text: str


class OCRBody(BaseModel):
    panel_id: str
    engine: str
    language: str | None = None


class ExtractBody(BaseModel):
    mode: Literal['incremental', 'full'] = 'incremental'
    base_run_id: str | None = None
    config_text: str | None = None


def create_app(store=None, adapters=None):
    store = store or ProjectStore()
    queue = JobQueue(store, adapters)

    @asynccontextmanager
    async def lifespan(app):
        yield
        queue.close()

    app = FastAPI(title='Manga2Animation', lifespan=lifespan)
    app.state.store, app.state.queue = store, queue

    @app.get('/api/jobs')
    def all_jobs():
        from .services.job_dashboard import list_jobs
        return list_jobs(store)

    @app.post('/api/jobs/cancel')
    def stop_job(body: dict):
        from .services.job_dashboard import cancel_job
        return cancel_job(store, queue, body)

    @app.get('/api/languages')
    def language_catalog():
        from .languages import catalog
        return catalog()

    @app.get('/api/fonts')
    def installed_fonts():
        from .services.subtitles import fonts
        return [{'name':font['name']} for font in fonts()]

    @app.exception_handler(ValueError)
    async def invalid(request, exc):
        return JSONResponse({'detail': str(exc)}, status_code=400)

    @app.exception_handler(FileNotFoundError)
    async def missing(request, exc):
        return JSONResponse({'detail': 'Không tìm thấy dữ liệu.'}, status_code=404)

    @app.exception_handler(yaml.YAMLError)
    async def invalid_yaml(request, exc):
        return JSONResponse({'detail': f'YAML không hợp lệ: {exc}'}, status_code=400)

    @app.exception_handler(UnidentifiedImageError)
    async def invalid_image(request, exc):
        return JSONResponse({'detail': 'File tải lên không phải ảnh hợp lệ.'}, status_code=400)

    @app.get('/api/projects')
    def projects():
        return store.list()

    @app.get('/api/projects/{pid}/pages/{page_id}/layout')
    def page_layout(pid: str, page_id: str, run_id: str | None = None):
        from PIL import Image
        from .services.page_layout import layout_from_page
        project = store.get(pid)
        source = next((p for p in project['pages'] if p['id'] == page_id), None)
        if source is None:
            raise HTTPException(404, 'Không tìm thấy trang.')
        with Image.open(safe_path(store.folder(pid), source['image'])) as image:
            size = list(image.size)
        layout = source.get('layout')
        if layout is None:
            runs = sorted((store.folder(pid)/'extracts').glob('*/manifest.json'), key=lambda p: p.stat().st_mtime, reverse=True)
            if run_id:
                runs.sort(key=lambda p: p.parent.name != run_id)
            for path in runs:
                page = next((p for p in read_json(path)['pages'] if p['id'] == page_id), None)
                if page:
                    edits = read_json(path.parent/'edits.json') if (path.parent/'edits.json').is_file() else None
                    layout = layout_from_page(page, edits)
                    break
        return {'size': size, 'layout': layout or {'panels': [], 'texts': []}, 'coordinate_system': 'original'}

    @app.post('/api/projects/{pid}/extracts/{rid}/videos')
    def create_video(pid: str, rid: str, body: dict):
        from .services.video import submit_video
        return submit_video(store, queue.executor, pid, rid, body)

    @app.get('/api/projects/{pid}/videos')
    def videos(pid: str):
        return sorted([read_json(p) for p in (store.folder(pid)/'videos').glob('*/status.json')], key=lambda s: s['created_at'], reverse=True)

    @app.get('/api/projects/{pid}/videos/{vid}')
    def video_status(pid: str, vid: str):
        if not __import__('re').fullmatch('[0-9a-f]{32}', vid):
            raise ValueError('ID video không hợp lệ.')
        return read_json(safe_path(store.folder(pid), 'videos/'+vid+'/status.json'))

    @app.post('/api/projects/{pid}/videos/{vid}/cancel')
    def cancel_video(pid: str, vid: str):
        if not __import__('re').fullmatch('[0-9a-f]{32}', vid):
            raise ValueError('ID video không hợp lệ.')
        folder = safe_path(store.folder(pid), 'videos/'+vid)
        state = read_json(folder/'status.json')
        if state['state'] in ('queued', 'running'):
            (folder/'cancel.requested').touch()
        return state

    @app.get('/api/capabilities')
    def capabilities():
        from .ocr.paddle import languages
        from .translation.google import language_list
        from .translation.llm import MODEL_PRESETS
        from .languages import ocr_capabilities
        import importlib.util
        return {'ocr_languages': ocr_capabilities(), 'translation_languages': language_list(),
                'translation_providers': [{'id':'googletrans','name':'Google Translate (googletrans)'},
                                          {'id':'ollama','name':'Ollama local'},
                                          {'id':'openai_compatible','name':'API tương thích OpenAI'}],
                'translation_models': MODEL_PRESETS,
                'paddleocr_installed': bool(importlib.util.find_spec('paddleocr')),
                'subtitle_segmentation': 'syllable_weighted_ass'}

    @app.post('/api/llm/models')
    def llm_models(body: dict):
        from .translation.llm import list_models
        provider = body.get('provider')
        if provider not in ('ollama','openai_compatible'):
            raise ValueError('Provider LLM không hợp lệ.')
        return list_models(provider,body.get('settings',{}))

    @app.delete('/api/projects/{pid}')
    def delete_project(pid: str):
        return store.delete_project(pid)

    @app.delete('/api/projects/{pid}/extracts/{rid}')
    def delete_run(pid: str, rid: str):
        return store.delete_run(pid, rid)

    @app.post('/api/projects/{pid}/extracts/{rid}/cancel')
    def cancel_run(pid: str, rid: str):
        return queue.cancel_extract(store.run_folder(pid, rid))

    @app.post('/api/projects/{pid}/voice-uploads')
    async def voice_upload(pid: str, file: UploadFile = File(...)):
        try:
            return store.upload_audio(pid, file.filename, await file.read())
        finally:
            await file.close()

    @app.get('/api/projects/{pid}/tasks')
    def tasks(pid: str):
        return queue.enrichment.list(pid)

    @app.post('/api/projects/{pid}/tasks')
    def submit_task(pid: str, body: dict):
        return queue.enrichment.submit(pid, body.get('operation'), body)

    @app.get('/api/projects/{pid}/tasks/{tid}')
    def task(pid: str, tid: str):
        return read_json(queue.enrichment.task_folder(pid, tid)/'status.json')

    @app.post('/api/projects/{pid}/tasks/{tid}/cancel')
    def cancel_task(pid: str, tid: str):
        folder = queue.enrichment.task_folder(pid, tid)
        current = read_json(folder/'status.json')
        if current['state'] in ('queued', 'running'):
            (folder/'cancel.requested').touch()
        return current

    @app.post('/api/projects/{pid}/tasks/{tid}/apply')
    def apply_task(pid: str, tid: str, body: dict):
        return queue.enrichment.apply(pid, tid, body)

    @app.post('/api/projects')
    def create(body: Name):
        return store.create(body.name)

    @app.get('/api/projects/{pid}')
    def project(pid: str):
        return store.get(pid)

    @app.put('/api/projects/{pid}')
    def update(pid: str, body: dict):
        return store.update(pid, body)

    @app.get('/api/projects/{pid}/config')
    def config(pid: str):
        return {'text': store.config(pid)}

    @app.put('/api/projects/{pid}/config')
    def save_config(pid: str, body: ConfigBody):
        return {'text': store.config(pid, body.text)}

    @app.post('/api/projects/{pid}/uploads')
    async def uploads(pid: str, files: list[UploadFile] = File(...), reference: bool = False):
        result = []
        for upload in files:
            try:
                result.append(store.upload(pid, upload.filename, await upload.read(), reference))
            finally:
                await upload.close()
        return result

    @app.post('/api/projects/{pid}/references/url')
    def reference_url(pid: str, body: dict):
        from urllib.request import urlopen, Request
        from urllib.parse import urlparse
        url = body.get('url', '')
        if urlparse(url).scheme not in ('http', 'https'):
            raise ValueError('Ảnh tham chiếu cần URL http hoặc https.')
        with urlopen(Request(url, headers={'User-Agent': 'Manga2Animation/1.0'}), timeout=30) as response:
            data = response.read(25*1024*1024+1)
        if len(data) > 25*1024*1024:
            raise ValueError('Ảnh tham chiếu quá 25 MB.')
        return store.upload(pid, 'reference.png', data, True)

    @app.get('/api/projects/{pid}/extracts')
    def runs(pid: str):
        return sorted([read_json(p) for p in (store.folder(pid)/'extracts').glob('*/status.json')],
                      key=lambda v: v['created_at'], reverse=True)

    @app.post('/api/projects/{pid}/extract-plan')
    def extract_plan(pid: str, body: ExtractBody):
        return store.extraction_plan(pid, body.base_run_id, body.mode == 'full', body.config_text)

    @app.post('/api/projects/{pid}/extracts')
    def start(pid: str, body: ExtractBody | None = None):
        body = body or ExtractBody()
        return queue.submit_extract(pid, body.base_run_id, body.mode == 'full')

    @app.get('/api/projects/{pid}/extracts/{rid}')
    def run(pid: str, rid: str):
        folder = store.run_folder(pid, rid)
        status = read_json(folder / 'status.json')
        return {'status': status,
                'manifest': read_json(folder / 'manifest.json') if (folder/'manifest.json').exists() else None,
                'edits': store.edits(folder) if (folder/'edits.json').exists() else None}

    @app.put('/api/projects/{pid}/extracts/{rid}/edits')
    def edits(pid: str, rid: str, body: dict):
        return store.edits(store.run_folder(pid, rid), body)

    @app.post('/api/projects/{pid}/extracts/{rid}/ocr')
    def ocr(pid: str, rid: str, body: OCRBody):
        if body.engine not in ENGINES:
            raise ValueError('OCR engine không hợp lệ.')
        return queue.submit_ocr(store.run_folder(pid, rid), body.panel_id, body.engine, {'language': body.language})

    @app.get('/api/projects/{pid}/extracts/{rid}/proposals/{proposal_id}')
    def proposal(pid: str, rid: str, proposal_id: str):
        return read_json(safe_path(store.run_folder(pid, rid)/'proposals', proposal_id+'.json'))

    @app.post('/api/projects/{pid}/extracts/{rid}/proposals/{proposal_id}/apply')
    def apply(pid: str, rid: str, proposal_id: str, body: dict):
        folder = store.run_folder(pid, rid)
        proposed = read_json(safe_path(folder/'proposals', proposal_id+'.json'))
        if proposed['state'] != 'completed':
            raise ValueError('OCR chưa hoàn tất.')
        edits = store.edits(folder)
        if body.get('revision') != edits['revision']:
            raise ValueError('Bản chỉnh sửa đã thay đổi; hãy lưu và thử lại.')
        old = {d['id']: d for d in edits['panels'][proposed['panel_id']]['dialogues']}
        edits['panels'][proposed['panel_id']]['dialogues'] = [
            {**d, 'speaker_id': old.get(d['id'], d)['speaker_id']} for d in proposed['dialogues']]
        return store.edits(folder, edits)

    @app.get('/api/projects/{pid}/artifacts/{asset:path}')
    def artifact(pid: str, asset: str):
        path = safe_path(store.folder(pid), asset)
        if not path.is_file():
            raise HTTPException(404)
        return FileResponse(path)

    @app.get('/{path:path}')
    def frontend(path: str):
        root = ROOT / 'frontend/dist'
        candidate = safe_path(root, path)
        if candidate.is_file():
            return FileResponse(candidate)
        if path.startswith('api/'):
            raise HTTPException(404)
        if (root/'index.html').exists():
            return FileResponse(root/'index.html')
        return JSONResponse({'detail': 'Chưa build UI. Chạy npm ci và npm run build trong frontend/.'}, status_code=503)
    return app
