"""Tính thời lượng từ văn bản/clip, không gọi model khi thay tốc độ đọc."""
import math
import re
from .translations import translation_of


def validate_timing(settings):
    if settings['mode'] not in ('manual', 'text', 'audio'):
        raise ValueError('Chế độ thời lượng phải là manual, text hoặc audio.')
    for key in ('min_seconds', 'words_per_minute', 'dialogue_gap'):
        value = settings[key]
        if not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError(f'Thời lượng: {key} không hợp lệ.')
    if settings['min_seconds'] <= 0 or settings['words_per_minute'] <= 0:
        raise ValueError('Số giây tối thiểu và tốc độ đọc phải lớn hơn 0.')
    if settings['text_source'] not in ('original', 'translation'):
        raise ValueError('Nguồn tính thời lượng không hợp lệ.')


def dialogue_text(dialogue, source, language=None):
    return translation_of(dialogue, language).get('text', '') if source == 'translation' else dialogue.get('text', '')


def word_count(text):
    # Chữ Việt tính theo đơn vị cách nhau bởi khoảng trắng; Nhật/Trung đếm từng chữ.
    return len(re.findall(r'[\u3040-\u30ff\u3400-\u9fff]|[^\W_\u3040-\u30ff\u3400-\u9fff]+', text, flags=re.UNICODE))


def valid_audio(dialogue, voice_ids=None):
    clip = dialogue.get('audio', {})
    return bool(clip.get('path') and clip.get('input_text') == dialogue_text(dialogue, clip.get('text_source', 'original'), clip.get('translation_language'))
                and clip.get('speaker_id') == dialogue.get('speaker_id') and clip.get('duration', 0) > 0
                and (voice_ids is None or voice_ids.get(dialogue.get('speaker_id'), voice_ids.get('unknown')) == clip.get('voice_id')))


def panel_duration(panel, global_settings, voice_ids=None):
    settings = {**global_settings, **panel.get('timing', {})}
    validate_timing(settings)
    if settings['mode'] == 'manual':
        return float(panel['duration']), 'manual'
    dialogues = [d for d in panel['dialogues'] if dialogue_text(d, settings['text_source'], settings.get('translation_language')).strip()]
    minimum = settings['min_seconds']
    if settings['mode'] == 'text':
        words = sum(word_count(dialogue_text(d, settings['text_source'], settings.get('translation_language'))) for d in dialogues)
        return round(minimum + words * 60 / settings['words_per_minute'], 3), 'text'
    if any(not valid_audio(d, voice_ids) for d in dialogues):
        # Chưa đủ âm thanh thì giữ thời lượng hiện có, không giả một độ dài audio.
        return max(minimum, float(panel['duration'])), 'audio_pending'
    return round(minimum + sum(effective_audio_duration(d) for d in dialogues)
                 + max(0, len(dialogues)-1)*settings['dialogue_gap'], 3), 'audio'


def update_durations(edits, settings, characters=None):
    voice_ids = {c['id']: c.get('voice', {}).get('prompt') for c in characters} if characters is not None else None
    for panel in edits['panels'].values():
        panel['duration'], panel['duration_source'] = panel_duration(panel, settings, voice_ids)
    return edits


def effective_audio_duration(line):
    """Cắt đầu/cuối và tắt tiếng chỉ là chỉnh sửa, không sửa tệp âm thanh gốc."""
    duration = line.get('audio', {}).get('duration', 0)
    edit = line.get('audio_edit', {})
    return 0 if edit.get('muted') else max(0, min(duration, edit.get('end', duration))-max(0, edit.get('start', 0)))
