"""Danh mục ngôn ngữ dùng chung cho giọng nói, dịch và OCR."""
import json
from pathlib import Path


def catalog():
    return json.loads((Path(__file__).parent/'data'/'languages.json').read_text(encoding='utf-8'))


def canonical_language(value):
    code=value.strip().lower()
    return next((item['code'] for item in catalog() if code==item['code'] or code in item.get('aliases', [])), code)


def engine_language(value,engine):
    """Mã chuẩn dùng cho UI, mã riêng chỉ chuyển đổi tại ranh giới gọi engine."""
    if engine=='tesseract' and '+' in value:
        return '+'.join(engine_language(code,engine) for code in value.split('+'))
    if engine=='tesseract' and value.endswith('_vert'):
        return value
    item=next((item for item in catalog() if value.lower() in [item['code'],*item.get('aliases',[]),*item.get('ocr_codes',{}).values()]),None)
    return item.get('ocr_codes',{}).get(engine,value) if item else value


def ocr_capabilities():
    from .ocr.paddle import languages
    result={'paddleocr':languages(),'tesseract':[]}
    for item in catalog():
        code=item.get('ocr_codes',{}).get('tesseract')
        if code:
            result['tesseract'].append({**item,'code':code})
            if code=='jpn':result['tesseract'].append({**item,'code':'jpn_vert','name':item['name']+' · chữ dọc'})
    return result
