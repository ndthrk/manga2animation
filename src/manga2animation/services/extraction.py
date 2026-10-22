"""Điều phối toàn trang: upscale một lần, Magi một lần, rồi OCR tùy chọn."""
from copy import deepcopy
from pathlib import Path
import yaml
from PIL import Image
from ..layout.geometry import area, intersection, pad_bbox, filter_panels, reading_order
from ..storage import read_json, write_json, now, safe_path
from ..domain import ManifestData
from ..ocr import normalize_text
from .models import ModelAdapters, release_models
from .gpu import gpu_serialized
from .cancellation import check_cancel, ExtractionCancelled
from ..settings import validate_config

COLORS = ['#6956b8', '#247e91', '#9a6239', '#8a4c78', '#48865d', '#626ab3']


def box_record(box, panel, sx, sy):
    return {'upscaled': box, 'original': [box[0]/sx, box[1]/sy, box[2]/sx, box[3]/sy],
            'panel': [box[0]-panel[0], box[1]-panel[1], box[2]-panel[0], box[3]-panel[1]] if panel else None}


def assign_region(box, panels, threshold):
    scores = [(intersection(box, p['bbox']) / max(area(box), 1), p) for p in panels]
    if not scores:
        return None
    score, panel = max(scores, key=lambda x: x[0])
    return panel if score >= threshold else None


def assemble_page(page, image, original_size, prediction, identities, cfg, folder):
    """Chuyển kết quả Magi thành metadata có ID, không bỏ vùng nằm ngoài panel."""
    width, height = image.size
    sx, sy = width / original_size[0], height / original_size[1]
    layout = page.get('layout')
    if layout is not None:
        prediction = deepcopy(prediction)
        prediction['panels'] = [[b*v for b, v in zip(p['bbox'], [sx, sy, sx, sy])] for p in layout['panels']]
        prediction['texts'] = [[b*v for b, v in zip(t['bbox'], [sx, sy, sx, sy])] for t in layout['texts']]
        prediction['text_character_associations'] = []
        prediction['is_essential_text'] = [True]*len(layout['texts'])
    panels = [{'id': f"{page['id']}_panel_{i}", 'bbox': pad_bbox(list(map(float, b)), image.size, 0),
               'detection_index': i} for i, b in enumerate(prediction['panels']) if area(b) > 0]
    if layout is not None:
        for p in panels:
            p['id'] = layout['panels'][p['detection_index']]['id']
    if layout is None or not layout.get('manual_order'):
        panels = reading_order(panels if layout is not None else filter_panels(panels, width*height, cfg['min_panel_area'], cfg['nested_ratio']), cfg['direction'])
    for i, panel in enumerate(panels):
        panel.update(order=i, texts=[], characters=[], image=f"panels/{panel['id']}.png")
        panel['coordinates'] = box_record(panel['bbox'], panel['bbox'], sx, sy)
        destination = folder / panel['image']
        destination.parent.mkdir(exist_ok=True)
        image.crop(panel['bbox']).save(destination)
    characters, texts = [], []
    known_ids = {c['id'] for c in read_json(folder / 'snapshot.json')['characters']}
    clusters = prediction.get('character_cluster_labels', list(range(len(prediction['characters']))))
    for i, b in enumerate(prediction['characters']):
        panel = assign_region(b, panels, cfg['text_overlap'])
        identity = identities[i] if i < len(identities) and (identities[i] in known_ids or str(identities[i]).startswith('unknown')) else f"unknown_{page['id']}_{clusters[i]}"
        item = {'id': f"{page['id']}_character_{i}", 'character_id': identity,
                'label': 'known' if identity in known_ids else 'unknown', 'detection_index': i,
                'panel_id': panel['id'] if panel else None,
                'bbox': box_record(list(map(float, b)), panel['bbox'] if panel else None, sx, sy)}
        characters.append(item)
        if panel:
            panel['characters'].append(item)
    associations = dict(prediction.get('text_character_associations', []))
    for i, b in enumerate(prediction['texts']):
        raw = list(map(float, b))
        panel = assign_region(raw, panels, cfg['text_overlap'])
        padded = pad_bbox(raw, image.size, cfg['text_padding'])
        speaker_index = associations.get(i)
        speaker = characters[speaker_index] if speaker_index is not None and 0 <= speaker_index < len(characters) else None
        item = {'id': f"{page['id']}_text_{i}", 'detection_index': i,
                'panel_id': panel['id'] if panel else None,
                'bbox': box_record(raw, panel['bbox'] if panel else None, sx, sy),
                'bbox_padded': box_record(padded, panel['bbox'] if panel else None, sx, sy),
                'speaker_id': speaker['character_id'] if speaker else f"unknown_speaker_{page['id']}_{i}",
                'speaker_instance_id': speaker['id'] if speaker else None,
                'essential': bool(prediction.get('is_essential_text', [True]*len(prediction['texts']))[i]),
                'ocr': {'status': 'pending', 'content': '', 'engine': None}}
        if layout is not None:
            item['id'] = layout['texts'][i]['id']
            item['speaker_id'] = layout['texts'][i].get('speaker_id') or 'unknown'
            item['speaker_instance_id'] = None
        texts.append(item)
        if panel:
            panel['texts'].append(item)
    for panel in panels:
        ordered = [{'bbox': t['bbox']['upscaled'], 'item': t} for t in panel['texts']]
        if layout is None or not layout.get('manual_text_order'):
            ordered = reading_order(ordered, cfg['direction'])
        panel['texts'] = [t['item'] for t in ordered]
        for order, text in enumerate(panel['texts']):
            text['order'] = order
    return {'id': page['id'], 'name': page['name'], 'source_image': page['image'],
            'upscaled_image': f"upscaled/{page['id']}.png", 'original_size': list(original_size),
            'upscaled_size': list(image.size), 'scale': [sx, sy], 'panels': panels,
            'layout_override': deepcopy(layout),
            'unassigned_texts': [t for t in texts if t['panel_id'] is None],
            'unassigned_characters': [c for c in characters if c['panel_id'] is None]}


def initial_edits(manifest, batch_size):
    panels = [p for page in manifest['pages'] for p in page['panels']]
    batches = [{'id': f'batch_{i}', 'color': COLORS[i % len(COLORS)], 'context': ''}
               for i in range((len(panels)+batch_size-1)//batch_size)]
    return {'schema_version': '1.0', 'revision': 0, 'order': [p['id'] for p in panels], 'batches': batches,
            'panels': {p['id']: {'hidden': False, 'duration': 4, 'prompt': '',
                        'batch_id': batches[i//batch_size]['id'],
                        'dialogues': [{'id': t['id'], 'text': normalize_text(t['ocr']['content']), 'speaker_id': t['speaker_id']}
                                      for t in p['texts']]} for i, p in enumerate(panels)}}


@gpu_serialized
def extract(folder, adapters=None, progress=None):
    folder = Path(folder)
    adapters = adapters or ModelAdapters()
    cfg = validate_config(yaml.safe_load((folder / 'config.yaml').read_text(encoding='utf-8')))
    snapshot = read_json(folder / 'snapshot.json')
    status = read_json(folder / 'status.json')
    from .incremental import signature, file_digest, merge_edits
    reuse = read_json(folder/'reuse.json') if (folder/'reuse.json').is_file() else {'pages': [], 'edits': None, 'plan': {}}
    reused = {p['id']: p for p in reuse['pages']}
    pages_to_process = [p for p in snapshot['pages'] if p['id'] not in reused]
    positions = {p['id']: i+1 for i, p in enumerate(snapshot['pages'])}
    model = processor = recognizer = upscaler = None
    used_models = bool(pages_to_process)

    def report(stage, page=0):
        check_cancel(folder)
        status.update(state='running', stage=stage, page=page, updated_at=now(),
                      reused_pages=len(reused), processing_pages=len(pages_to_process))
        write_json(folder / 'status.json', status)
        if progress:
            progress(deepcopy(status))
    try:
        report('reuse')
        actual_signature = signature(folder, snapshot, cfg)
        if reuse['plan'].get('processing_signature', actual_signature) != actual_signature:
            raise ValueError('Model đã thay đổi sau khi tạo job. Hãy trích xuất lại để tránh trộn hai phiên bản.')
        manifest = {'schema_version': '1.0', 'run_id': folder.name, 'created_at': now(),
                    'processing_signature': actual_signature,
                    'coordinate_system': 'xyxy; pixel; gốc trên trái; biên phải/dưới không thuộc vùng crop',
                    'models': {'layout': 'magi_v2', 'upscale': cfg['upscale'], 'magi': cfg['magi'], 'ocr': cfg['ocr']},
                    'incremental': {**reuse['plan'], 'reused_pages': len(reused), 'processing_pages': len(pages_to_process)},
                    'global_prompt': snapshot['global_prompt'], 'characters': snapshot['characters'], 'pages': []}
        new_pages = []
        if pages_to_process:
            report('upscale')
            upscaler = adapters.upscaler(cfg['upscale'])
            originals = []
            (folder / 'upscaled').mkdir(exist_ok=True)
            for page in pages_to_process:
                report('upscale', positions[page['id']])
                with Image.open(folder / page['image']) as source:
                    source = source.convert('RGB')
                    originals.append(source.size)
                    scale=cfg['upscale']['scale']
                    enhanced = upscaler.upscale(source, scale=scale)
                    if enhanced.size != (round(source.width*scale), round(source.height*scale)):
                        raise ValueError(f'Upscaler không trả ảnh đúng kích thước ×{scale}.')
                    enhanced.save(folder / f"upscaled/{page['id']}.png")
            upscaler = None
            release_models()
            report('load_magi')
            model, processor = adapters.magi(cfg['magi'])
            predictions, images = [], []
            for page in pages_to_process:
                report('detection', positions[page['id']])
                with Image.open(folder / f"upscaled/{page['id']}.png") as image:
                    images.append(image.convert('RGB'))
                prediction = adapters.detect(model, images[-1], cfg['magi'])
                predictions.append(prediction)
                write_json(folder / 'detections' / (page['id']+'.json'), prediction)
            report('identity')
            identities = iter(adapters.identify(model, images, predictions, snapshot['characters'], folder))
            for i, (page, image, prediction) in enumerate(zip(pages_to_process, images, predictions)):
                report('layout', positions[page['id']])
                names = [next(identities, 'Other') for _ in prediction['characters']]
                result = assemble_page(page, image, originals[i], prediction, names, cfg, folder)
                result['inference_run_id'] = folder.name
                new_pages.append(result)
            engine = cfg['ocr']['engine']
            if cfg['ocr']['enabled']:
                if engine != 'magi_v2':
                    model = processor = None
                    release_models()
                    model, processor = adapters.magi(cfg['magi'], 'v3') if engine == 'magi_v3' else (None, None)
                recognizer = adapters.recognizer(engine, cfg, model, processor)
                for page, image in zip(new_pages, images):
                    report('ocr', positions[page['id']])
                    texts = [t for panel in page['panels'] for t in panel['texts']] + page['unassigned_texts']
                    if engine == 'magi_v2' and texts:
                        results = recognizer.recognize_regions(image, [t['bbox_padded']['upscaled'] for t in texts],
                                      batch_size=cfg['ocr']['batch_size'], max_new_tokens=cfg['ocr']['max_new_tokens'])
                    else:
                        results = []
                        for text in texts:
                            check_cancel(folder)
                            results.append(recognizer.recognize(image.crop(text['bbox_padded']['upscaled'])))
                    for text, result in zip(texts, results):
                        text['ocr'] = {'status': 'recognized', 'engine': engine, **result,
                                       'raw_content': result.get('content', ''), 'content': normalize_text(result.get('content', ''))}
                recognizer = None
            model = processor = None
            release_models()
        # Trang đã có ảnh upscale chỉ cần cắt/OCR lại vùng người dùng sửa, không gọi lại detect.
        layout_changes = {}
        for source in snapshot['pages']:
            old = reused.get(source['id'])
            if old is None or source.get('layout') == old.get('layout_override'):
                continue
            if source.get('layout') is None:
                continue
            report('layout', positions[source['id']])
            old_texts = {t['id']: t for p in old['panels'] for t in p['texts']}
            char_regions = sorted([c for p in old['panels'] for c in p['characters']]+old.get('unassigned_characters', []), key=lambda c: c['detection_index'])
            prediction = {'panels': [], 'texts': [], 'characters': [c['bbox']['upscaled'] for c in char_regions]}
            with Image.open(folder/old['upscaled_image']) as loaded:
                image = loaded.convert('RGB')
            revised = assemble_page(source, image, old['original_size'], prediction, [c['character_id'] for c in char_regions], cfg, folder)
            revised['reused_from'] = old.get('reused_from')
            changed = []
            for p in revised['panels']:
                for text in p['texts']:
                    previous = old_texts.get(text['id'])
                    if previous and previous['bbox']['original'] == text['bbox']['original']:
                        text['ocr'] = deepcopy(previous['ocr'])
                    else:
                        changed.append(text)
            if cfg['ocr']['enabled'] and changed:
                used_models = True
                engine = cfg['ocr']['engine']
                model, processor = adapters.magi(cfg['magi'], engine.replace('magi_', '')) if engine.startswith('magi_') else (None, None)
                recognizer = adapters.recognizer(engine, cfg, model, processor)
                report('ocr', positions[source['id']])
                for text in changed:
                    check_cancel(folder)
                    result = recognizer.recognize(image.crop(text['bbox_padded']['upscaled']))
                    text['ocr'] = {'status': 'recognized', 'engine': engine, **result,
                                   'raw_content': result.get('content', ''), 'content': normalize_text(result.get('content', ''))}
                model = processor = recognizer = None
                release_models()
            layout_changes[source['id']] = (old_texts, revised)
            reused[source['id']] = revised
        combined = {**reused, **{p['id']: p for p in new_pages}}
        for source in snapshot['pages']:
            page = combined[source['id']]
            page.update(name=source['name'], source_image=source['image'], source_sha256=file_digest(folder/source['image']))
            manifest['pages'].append(page)
        check_cancel(folder)
        write_json(folder / 'manifest.json', manifest)
        from .timing import update_durations
        edits = merge_edits(manifest, initial_edits(manifest, cfg['batch_size']), reuse['edits'], COLORS, cfg['batch_size'])
        for old_texts, page in layout_changes.values():
            if (page.get('layout_override') or {}).get('manual_order'):
                # Thứ tự vừa sửa ở trang phải tới được timeline, không bị bản cũ ghi đè.
                ordered_ids = [p['id'] for p in page['panels']]
                positions = [i for i, ident in enumerate(edits['order']) if ident in ordered_ids]
                batches = [edits['panels'][edits['order'][i]]['batch_id'] for i in positions]
                for index, ident, batch_id in zip(positions, ordered_ids, batches):
                    edits['order'][index] = ident
                    edits['panels'][ident]['batch_id'] = batch_id
            previous_lines = {d['id']: d for p in (reuse['edits'] or {}).get('panels', {}).values() for d in p['dialogues']}
            for p in page['panels']:
                lines = []
                for t in p['texts']:
                    old = old_texts.get(t['id'])
                    same_box = old and old['bbox']['original'] == t['bbox']['original']
                    line = deepcopy(previous_lines[t['id']]) if same_box and t['id'] in previous_lines else {'id': t['id'], 'text': t['ocr']['content']}
                    line['speaker_id'] = t['speaker_id']
                    lines.append(line)
                edits['panels'][p['id']]['dialogues'] = lines
        update_durations(edits, cfg['timing'], snapshot['characters'])
        write_json(folder / 'edits.json', edits)
        status.update(state='completed', stage='completed', page=len(snapshot['pages']), updated_at=now())
        write_json(folder / 'status.json', status)
        return ManifestData(manifest, folder)
    except ExtractionCancelled as exc:
        status.update(state='cancelled', stage='cancelled', error=str(exc), updated_at=now())
        write_json(folder / 'status.json', status)
        return None
    except Exception as exc:
        import traceback
        status.update(state='failed', error=str(exc), traceback=traceback.format_exc(), updated_at=now())
        write_json(folder / 'status.json', status)
        raise
    finally:
        model = processor = recognizer = upscaler = None
        if used_models:
            release_models()


def load_panel_images(manifest, split_panel=False):
    """Nhận đường dẫn JSON hoặc dict có _base_dir; trả metadata và ảnh PIL độc lập."""
    if isinstance(manifest, (str, Path)):
        path = Path(manifest)
        data, base = read_json(path), path.parent
    else:
        data, base = manifest, Path(getattr(manifest, 'base_dir', manifest.get('_base_dir', '.')))
    output = []
    for page in data['pages']:
        for panel in page['panels']:
            with Image.open(safe_path(base, page['upscaled_image'] if split_panel else panel['image'])) as image:
                crop = image.crop(panel['bbox']) if split_panel else image.copy()
                output.append({'panel': deepcopy(panel), 'image': crop})
    return output
