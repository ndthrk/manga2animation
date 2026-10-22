"""Vùng cắt do người dùng sửa luôn dùng tọa độ trang gốc, không sửa manifest cũ."""
from copy import deepcopy
import math
import re


def validate_layout(layout, size):
    if not isinstance(layout, dict):
        raise ValueError('Bố cục trang phải là một đối tượng.')
    result = deepcopy(layout)
    for option in ('manual_order', 'manual_text_order'):
        if option in result and not isinstance(result[option], bool):
            raise ValueError('Cờ thứ tự thủ công phải là boolean.')
    for kind in ('panels', 'texts'):
        if not isinstance(result.get(kind), list):
            raise ValueError('Bố cục cần danh sách panels và texts.')
        ids = []
        for region in result[kind]:
            ident = region.get('id', '')
            if not isinstance(ident, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,160}', ident):
                raise ValueError('ID vùng cắt không hợp lệ.')
            ids.append(ident)
            box = region.get('bbox')
            if not isinstance(box, list) or len(box) != 4 or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in box):
                raise ValueError('BBox cần bốn số hữu hạn theo dạng x1,y1,x2,y2.')
            if not (0 <= box[0] < box[2] <= size[0] and 0 <= box[1] < box[3] <= size[1]):
                raise ValueError('Vùng cắt phải có diện tích dương và nằm trong trang gốc.')
            if kind == 'texts' and not isinstance(region.get('speaker_id', 'unknown'), str):
                raise ValueError('ID người nói phải là chuỗi.')
        if len(ids) != len(set(ids)):
            raise ValueError('ID vùng cắt không được trùng nhau.')
    return result


def layout_from_page(page, edits=None):
    dialogues = {d['id']: d for p in (edits or {}).get('panels', {}).values() for d in p['dialogues']}
    return {'panels': [{'id': p['id'], 'bbox': p['coordinates']['original']} for p in page['panels']],
            'texts': [{'id': t['id'], 'bbox': t['bbox']['original'],
                       'speaker_id': dialogues.get(t['id'], t).get('speaker_id', 'unknown')}
                      for p in page['panels'] for t in p['texts']]+[
                      {'id': t['id'], 'bbox': t['bbox']['original'], 'speaker_id': t['speaker_id']}
                      for t in page.get('unassigned_texts', [])]}
