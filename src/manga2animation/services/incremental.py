"""Tái sử dụng trang còn hợp lệ và nối trang mới, giữ bản chỉnh sửa cũ độc lập."""
from copy import deepcopy
from datetime import datetime
from functools import lru_cache
import hashlib
import importlib.metadata
import json
from pathlib import Path
import shutil
import yaml
from ..settings import ROOT, validate_config
from ..storage import read_json, write_json, safe_path, uid

PIPELINE_VERSION = 'magi-v2-layout-1'


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def file_digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


@lru_cache(maxsize=32)
def package_version(name):
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def processing_settings(cfg):
    """Prompt, thời lượng, giọng và màu nhân vật không làm mất cache detect/OCR."""
    keys = ('direction', 'min_panel_area', 'nested_ratio', 'text_overlap', 'text_padding', 'upscale', 'magi')
    value = {key: cfg[key] for key in keys}
    ocr = cfg['ocr']
    value['ocr'] = {'enabled': ocr['enabled']}
    if ocr['enabled']:
        engine = ocr['engine']
        value['ocr'].update(engine=engine)
        if engine.startswith('magi_'):
            value['ocr'].update(batch_size=ocr['batch_size'], max_new_tokens=ocr['max_new_tokens'])
        else:
            value['ocr']['options'] = ocr[engine]
    return value


def model_stamps(cfg):
    """Đọc kích thước/mtime trọng số, không băm hàng GB mỗi khi bấm nút."""
    paths = [cfg['upscale']['model'], cfg['magi']['model'], cfg['magi']['processor']]
    if cfg['ocr']['enabled']:
        engine = cfg['ocr']['engine']
        if engine == 'magi_v3': paths.append(cfg['magi']['v3_model'])
        if engine == 'indra': paths.append(cfg['ocr']['indra']['model'])
        if engine == 'tesseract' and cfg['ocr']['tesseract'].get('command'):
            paths.append(cfg['ocr']['tesseract']['command'])
            executable = Path(cfg['ocr']['tesseract']['command'])
            paths.extend(str(executable.parent/'tessdata'/(language+'.traineddata'))
                         for language in cfg['ocr']['tesseract']['language'].split('+'))
        if engine == 'paddleocr':
            paths.extend(cfg['ocr']['paddleocr'].get(k, '') for k in ('detection_model_dir', 'recognition_model_dir'))
            if not cfg['ocr']['paddleocr'].get('recognition_model_dir'):
                paths.append(str(Path.home()/'.paddlex/official_models'))
    stamps = []
    for value in filter(None, paths):
        path = (ROOT/value).resolve()
        files = [path] if path.is_file() else [p for p in path.rglob('*') if p.suffix.lower() in
                 ('.json','.txt','.py','.pt','.pth','.bin','.safetensors','.onnx','.model','.pdiparams','.pdmodel')] if path.is_dir() else []
        for file in sorted(files):
            info = file.stat()
            stamps.append([str(file), info.st_size, info.st_mtime_ns])
    return stamps


def signature(folder, project, cfg, stamps=None):
    bank = []
    for character in sorted(project['characters'], key=lambda c: c['id']):
        image = character.get('image')
        bank.append({'id': character['id'], 'image_sha256': file_digest(safe_path(folder, image)) if image else None})
    versions = {name: package_version(name) for name in ('torch', 'transformers', 'Pillow', 'numpy')}
    if cfg['ocr']['enabled']:
        package = {'tesseract':'pytesseract', 'indra':'indra-ocr', 'paddleocr':'paddleocr'}.get(cfg['ocr']['engine'])
        if package: versions[package] = package_version(package)
    return digest({'pipeline': PIPELINE_VERSION, 'processing': processing_settings(cfg), 'characters': bank,
                   'model_files': model_stamps(cfg) if stamps is None else stamps, 'packages': versions})


def make_plan(project_folder, project, cfg, base_run_id=None, force=False):
    folder = Path(project_folder)
    stamps = model_stamps(cfg)
    current_signature = signature(folder, project, cfg, stamps)
    plan = {'mode': 'full' if force else 'incremental', 'base_run_id': None, 'reused_page_ids': [],
            'processing_signature': current_signature, 'total': len(project['pages']), 'reasons': {}}
    candidates = []
    for status_path in (folder/'extracts').glob('*/status.json'):
        state = read_json(status_path)
        if state['state'] == 'completed': candidates.append((state['created_at'], status_path.parent))
    candidates.sort(reverse=True)
    if base_run_id:
        candidates.sort(key=lambda entry: entry[1].name != base_run_id)
    if force or not candidates:
        plan.update(reused_pages=0, processing_pages=len(project['pages']), reason='forced' if force else 'first_run')
        return plan
    baseline = candidates[0][1]
    plan['base_run_id'] = baseline.name
    try:
        old = read_json(baseline/'manifest.json')
        old_project = read_json(baseline/'snapshot.json')
        old_cfg = validate_config(yaml.safe_load((baseline/'config.yaml').read_text(encoding='utf-8')))
        old_signature = old.get('processing_signature')
        if old_signature is None:
            # Tương thích Extract cũ: ảnh/config phải khớp, model không được thay sau lần chạy đó.
            created = datetime.fromisoformat(old['created_at']).timestamp()
            changed_model = any(stamp[2]/1e9 > created for stamp in stamps)
            old_signature = signature(baseline, old_project, old_cfg, stamps) if not changed_model else 'changed_model'
        same_processing = old_signature == current_signature
        previous = {page['id']: page for page in old['pages']}
        for page in project['pages']:
            prior = previous.get(page['id'])
            reason = 'new_page' if prior is None else 'settings_changed' if not same_processing else None
            if prior and same_processing and page.get('layout') is None and prior.get('layout_override') is not None:
                reason = 'layout_reset'
            if prior and same_processing:
                try:
                    prior_digest = prior.get('source_sha256') or file_digest(safe_path(baseline, prior['source_image']))
                    current_digest = file_digest(safe_path(folder, page['image']))
                    if current_digest != prior_digest:
                        reason = 'image_changed'
                    else:
                        assets = [prior['upscaled_image']] + [p['image'] for p in prior['panels']]
                        if not all(safe_path(baseline, path).is_file() for path in assets): reason = 'missing_artifacts'
                        elif not (baseline/'edits.json').is_file(): reason = 'missing_edits'
                except (OSError, KeyError, ValueError):
                    reason = 'missing_artifacts'
            if reason:
                plan['reasons'][page['id']] = reason
            else:
                plan['reused_page_ids'].append(page['id'])
    except (OSError, KeyError, ValueError):
        plan['reason'] = 'invalid_baseline'
        plan['reused_page_ids'] = []
    plan.update(reused_pages=len(plan['reused_page_ids']), processing_pages=len(project['pages'])-len(plan['reused_page_ids']))
    return plan


def snapshot_reuse(project_folder, destination, plan):
    """Sao chép ngay lúc tạo job để xóa/sửa Extract cũ không làm hỏng lần mới."""
    destination = Path(destination)
    if not plan['reused_page_ids']:
        write_json(destination/'reuse.json', {'plan': plan, 'pages': [], 'edits': None})
        return
    baseline = safe_path(project_folder, 'extracts/'+plan['base_run_id'])
    manifest = read_json(baseline/'manifest.json')
    pages = [deepcopy(p) for p in manifest['pages'] if p['id'] in plan['reused_page_ids']]
    snapshot = read_json(destination/'snapshot.json')
    sources = {p['id']: p for p in snapshot['pages']}
    for page in pages[:]:
        prior_hash = page.get('source_sha256') or file_digest(safe_path(baseline,page['source_image']))
        if file_digest(safe_path(destination,sources[page['id']]['image'])) != prior_hash:
            pages.remove(page)
            plan['reasons'][page['id']] = 'image_changed'
    plan['reused_page_ids'] = [p['id'] for p in pages]
    plan.update(reused_pages=len(pages), processing_pages=plan['total']-len(pages))
    if not pages:
        write_json(destination/'reuse.json', {'plan': plan, 'pages': [], 'edits': None})
        return
    edits = read_json(baseline/'edits.json')
    retained = {p['id'] for page in pages for p in page['panels']}
    edits['order'] = [pid for pid in edits['order'] if pid in retained]
    edits['panels'] = {pid: value for pid, value in edits['panels'].items() if pid in retained}
    for page in pages:
        artifacts = [page['upscaled_image']] + [panel['image'] for panel in page['panels']]
        raw = f"detections/{page['id']}.json"
        if (baseline/raw).is_file(): artifacts.append(raw)
        for relative in artifacts:
            target = safe_path(destination, relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(safe_path(baseline, relative), target)
        page['reused_from'] = plan['base_run_id']
    for panel in edits['panels'].values():
        for dialogue in panel['dialogues']:
            audio = dialogue.get('audio')
            if audio and audio.get('path'):
                source = safe_path(project_folder, audio['path'])
                if source.is_file():
                    target = destination/'audio'/'reused'/(uid()+source.suffix)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)
                    audio['path'] = str(target.relative_to(project_folder)).replace('\\','/')
                else:
                    dialogue.pop('audio', None)
    write_json(destination/'reuse.json', {'plan': plan, 'pages': pages, 'edits': edits})


def merge_edits(manifest, fresh, reused, colors, batch_size):
    """Giữ timeline/batch đã review; panel mới được nối cuối theo thứ tự trang mới."""
    if not reused:
        return fresh
    result = deepcopy(reused)
    result['revision'] = 0
    result.pop('saved_at', None)
    new_ids = [pid for pid in fresh['order'] if pid not in result['panels']]
    result['order'] = [pid for pid in result['order'] if pid in fresh['panels']]
    result['panels'] = {pid: p for pid, p in result['panels'].items() if pid in fresh['panels']}
    for index in range(0, len(new_ids), batch_size):
        batch = {'id': 'batch_'+uid(), 'color': colors[len(result['batches']) % len(colors)], 'context': ''}
        result['batches'].append(batch)
        for pid in new_ids[index:index+batch_size]:
            result['panels'][pid] = deepcopy(fresh['panels'][pid])
            result['panels'][pid]['batch_id'] = batch['id']
            result['order'].append(pid)
    result['inherited_from'] = manifest['incremental']['base_run_id']
    return result
