"""Các bản dịch được lưu theo mã ngôn ngữ; vẫn đọc được dữ liệu cũ."""


def translation_of(line, language=None):
    if language:
        value = line.get('translations', {}).get(language)
        if value is not None:
            return value
        old = line.get('translation') or {}
        return old if old.get('target') == language else {}
    return line.get('translation') or next(iter(line.get('translations', {}).values()), {})


def set_translation(line, value):
    # Chỉ thay đúng ngôn ngữ đích, không làm mất các bản dịch khác.
    old = line.get('translation')
    versions = line.setdefault('translations', {})
    if old and old.get('target'):
        versions.setdefault(old['target'], old)
    versions[value['target']] = value
    line['translation'] = value
