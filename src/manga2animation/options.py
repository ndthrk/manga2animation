"""Mặc định tính năng bổ sung; project cũ vẫn đọc được mà không sửa snapshot."""
from copy import deepcopy
from .services.subtitles import DEFAULTS as SUBTITLE_DEFAULTS

EXTRA_DEFAULTS = {
    'video': {'width': 1280, 'height': 720, 'fps': 24, 'crf': 23,
              'include_audio': True, 'extend_for_audio': True, 'background': '#111111', 'subtitles': SUBTITLE_DEFAULTS},
    'translation': {'provider': 'googletrans', 'source': 'auto', 'target': 'vi',
                    'batch_size': 16, 'timeout_seconds': 30, 'max_words_per_screen': 12,
                    'request_interval': 1.0, 'retries': 2, 'batch_requests':True, 'max_chars_per_request':4000,
                    'ollama': {'base_url':'http://127.0.0.1:11434','model':'qwen3:1.7b',
                               'temperature':.2,'max_tokens':2048,'context_length':4096,
                               'timeout_seconds':120,'system_prompt':'','api_key_env':'','api_key':''},
                    'openai_compatible': {'base_url':'https://api.openai.com/v1','model':'gpt-4.1-mini',
                               'temperature':.2,'max_tokens':2048,'token_parameter':'max_tokens',
                               'timeout_seconds':120,'system_prompt':'','api_key_env':'LLM_API_KEY','api_key':'',
                               'json_mode':False,'send_temperature':True}},
    'timing': {'mode': 'manual', 'min_seconds': 1.0, 'words_per_minute': 180,
               'text_source': 'original', 'translation_language': 'vi', 'dialogue_gap': 0.2},
    'audio': {'provider': 'omnivoice', 'text_source': 'original', 'batch_size': 1,
              'language': 'vi', 'translation_language': 'vi', 'speed': 1.0, 'num_step': 32, 'guidance_scale': 2.0,
              'position_temperature': 5.0, 'class_temperature': 0.0, 'denoise': True,
              'preprocess_prompt': True, 'postprocess_output': True,
              'omnivoice': {'model': 'checkpoints/omnivoice', 'device': 'cuda:0', 'dtype': 'float16',
                            'python_executable': '', 'python_path': 'vendor/omnivoice',
                            'asr_model': 'checkpoints/whisper-small', 'asr_device': 'cuda:0',
                            'keep_alive_seconds': 60, 'timeout_seconds': 1800}},
}
PADDLE_DEFAULTS = {'language': 'vi', 'ocr_version': 'PP-OCRv5', 'device': 'cpu',
                   'detection_model_dir': '', 'recognition_model_dir': ''}


def merge_defaults(current, defaults):
    result = deepcopy(defaults)
    for key, value in current.items():
        result[key] = merge_defaults(value, result[key]) if isinstance(value, dict) and isinstance(result.get(key), dict) else deepcopy(value)
    return result


def with_defaults(cfg):
    result = merge_defaults(cfg, EXTRA_DEFAULTS)
    result['ocr']['paddleocr'] = merge_defaults(result['ocr'].get('paddleocr', {}), PADDLE_DEFAULTS)
    return result
