"""Đọc YAML và kiểm tra cấu hình trước khi đưa vào hàng đợi."""
from copy import deepcopy
from pathlib import Path
import yaml
from .options import with_defaults

ROOT = Path(__file__).resolve().parents[2]
ENGINES = ('tesseract', 'indra', 'magi_v2', 'magi_v3', 'paddleocr')


def read_config(path=None):
    local=ROOT/'configs/pipeline.local.yaml'
    path = Path(path or (local if local.is_file() else ROOT/'configs/pipeline.yaml'))
    return validate_config(yaml.safe_load(path.read_text(encoding='utf-8')))


def validate_config(value):
    try:
        return _validate_config(value)
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError(f'Cấu hình thiếu trường hoặc sai kiểu dữ liệu: {exc}') from exc


def _validate_config(value):
    if not isinstance(value, dict):
        raise ValueError('Cấu hình phải là một ánh xạ YAML.')
    cfg = deepcopy(value)
    required = {'direction', 'min_panel_area', 'nested_ratio', 'text_overlap', 'text_padding',
                'batch_size', 'upscale', 'magi', 'ocr'}
    if not required <= cfg.keys():
        raise ValueError(f'Thiếu cấu hình: {sorted(required - cfg.keys())}')
    if cfg['direction'] not in ('jp', 'vn'):
        raise ValueError('Hướng đọc phải là jp hoặc vn.')
    for key in ('min_panel_area', 'nested_ratio', 'text_overlap'):
        if not 0 < float(cfg[key]) <= 1:
            raise ValueError(f'{key} phải trong (0, 1].')
    if not 0 <= float(cfg['text_padding']) <= 1 or not isinstance(cfg['batch_size'], int) or cfg['batch_size'] < 1:
        raise ValueError('Padding phải trong [0, 1], số panel mỗi batch phải dương.')
    scale=cfg['upscale'].get('scale',2)
    if isinstance(scale,bool) or not isinstance(scale,(int,float)) or not 1<=scale<=4:
        raise ValueError('Tỉ lệ upscale phải trong [1, 4].')
    cfg['upscale']['scale']=scale
    if cfg['ocr']['engine'] not in ENGINES or not isinstance(cfg['ocr']['enabled'], bool):
        raise ValueError('OCR cần enabled kiểu boolean và engine hợp lệ.')
    for key in ('panel_detection_threshold', 'text_detection_threshold', 'character_detection_threshold'):
        if not 0 < cfg['magi'][key] <= 1:
            raise ValueError(f'{key} phải trong (0, 1].')
    if cfg['upscale']['tile'] < 1 or cfg['magi']['threads'] < 1:
        raise ValueError('Tile và số luồng phải dương.')
    for section, key in [('upscale', 'model'), ('upscale', 'device'), ('magi', 'model'),
                         ('magi', 'processor'), ('magi', 'v3_model'), ('magi', 'device')]:
        if not isinstance(cfg[section][key], str) or not cfg[section][key].strip():
            raise ValueError(f'{section}.{key} phải là chuỗi không rỗng.')
    for key, threshold in cfg['magi'].items():
        if key.endswith('_threshold') and not 0 < threshold <= 1:
            raise ValueError(f'{key} phải trong (0, 1].')
    for value in (cfg['upscale']['tile'], cfg['magi']['threads'], cfg['ocr']['batch_size'], cfg['ocr']['max_new_tokens']):
        if not isinstance(value, int) or value < 1:
            raise ValueError('Tile, số luồng và kích thước batch/token phải là số nguyên dương.')
    if not isinstance(cfg['ocr']['tesseract']['psm'], int) or not 3 <= cfg['ocr']['tesseract']['psm'] <= 13:
        raise ValueError('Tesseract PSM phải trong [3, 13].')
    if not cfg['ocr']['tesseract']['language'] or not cfg['ocr']['indra']['model']:
        raise ValueError('Cần ngôn ngữ Tesseract và đường dẫn model Indra.')
    cfg = with_defaults(cfg)
    from .services.subtitles import validate_subtitles
    cfg['video']['subtitles']=validate_subtitles(cfg['video'].get('subtitles'))
    from .services.timing import validate_timing
    from .services.video import validate_video
    cfg['video'] = validate_video(cfg['video'])
    validate_timing(cfg['timing'])
    if cfg['translation']['provider'] not in ('googletrans','ollama','openai_compatible') or not 1 <= cfg['translation']['batch_size'] <= 100:
        raise ValueError('Provider dịch hoặc batch dịch không hợp lệ.')
    if not isinstance(cfg['translation']['batch_requests'],bool) or not 128 <= cfg['translation']['max_chars_per_request'] <= 14000:
        raise ValueError('Cấu hình gộp request hoặc giới hạn ký tự dịch không hợp lệ.')
    targets = cfg['translation'].get('targets', [])
    if not isinstance(targets, list) or len(targets) > 20 or any(not isinstance(t, str) or not t.strip() for t in targets):
        raise ValueError('Ngôn ngữ đích cần là danh sách tối đa 20 mã ngôn ngữ.')
    for provider in ('ollama','openai_compatible'):
        options = cfg['translation'][provider]
        if (not isinstance(options,dict) or not isinstance(options.get('model'),str)
                or not 1 <= options.get('max_tokens',0) <= 32768 or not 1 <= options.get('timeout_seconds',0) <= 1800):
            raise ValueError('Cấu hình model/token/timeout LLM không hợp lệ.')
    if not 1 <= cfg['audio']['batch_size'] <= 8 or not .25 <= cfg['audio']['speed'] <= 4:
        raise ValueError('Batch âm thanh phải trong [1, 8], tốc độ trong [0.25, 4].')
    if not 1 <= cfg['audio']['num_step'] <= 256 or cfg['audio']['text_source'] not in ('original', 'translation'):
        raise ValueError('Số bước hoặc nguồn văn bản âm thanh không hợp lệ.')
    return cfg


def model_path(value):
    return str((ROOT / value).resolve())
