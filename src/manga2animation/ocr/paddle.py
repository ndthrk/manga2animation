"""PaddleOCR 3.x: đọc cả vùng thoại, giữ từng dòng và độ tin cậy."""
LANGUAGE_CODES = '''ch chinese_cht en japan korean th el te ta af az bs cs cy da de es et fr ga hr hu id is it ku la lt lv mi ms mt nl no oc pi pl pt ro rs_latin sk sl sq sv sw tl tr uz vi french german fi eu gl lb rm ca qu ar fa ug ur ps sd bal ru be uk rs_cyrillic bg mn abq ady kbd ava dar inh che lbe lez tab kk ky tg mk tt cv ba mhr mo udm kv os bua xal tyv sah kaa hi mr ne bh mai ang bho mah sck new gom sa bgc'''.split()
LANGUAGE_NAMES = {'vi':'Tiếng Việt', 'en':'English', 'japan':'日本語 · Tiếng Nhật', 'korean':'한국어 · Tiếng Hàn',
                  'ch':'中文 giản thể', 'chinese_cht':'中文 phồn thể', 'th':'Tiếng Thái', 'fr':'Français',
                  'de':'Deutsch', 'german':'Deutsch', 'french':'Français', 'es':'Español', 'pt':'Português',
                  'ru':'Русский', 'id':'Bahasa Indonesia', 'it':'Italiano', 'ar':'العربية', 'hi':'हिन्दी'}
LANGUAGE_NAMES.update(dict(zip(
    '''th el te ta af az bs cs cy da et ga hr hu is ku la lt lv mi ms mt nl no oc pi pl ro rs_latin sk sl sq sv sw tl tr uz fi eu gl lb rm ca qu fa ug ur ps sd bal be uk rs_cyrillic bg mn abq ady kbd ava dar inh che lbe lez tab kk ky tg mk tt cv ba mhr mo udm kv os bua xal tyv sah kaa mr ne bh mai ang bho mah sck new gom sa bgc'''.split(),
    '''Thai|Greek|Telugu|Tamil|Afrikaans|Azerbaijani|Bosnian|Czech|Welsh|Danish|Estonian|Irish|Croatian|Hungarian|Icelandic|Kurdish|Latin|Lithuanian|Latvian|Maori|Malay|Maltese|Dutch|Norwegian|Occitan|Pali|Polish|Romanian|Serbian (Latin)|Slovak|Slovenian|Albanian|Swedish|Swahili|Tagalog|Turkish|Uzbek|Finnish|Basque|Galician|Luxembourgish|Romansh|Catalan|Quechua|Persian|Uyghur|Urdu|Pashto|Sindhi|Balochi|Belarusian|Ukrainian|Serbian (Cyrillic)|Bulgarian|Mongolian|Abaza|Adyghe|Kabardian|Avar|Dargwa|Ingush|Chechen|Lak|Lezghian|Tabassaran|Kazakh|Kyrgyz|Tajik|Macedonian|Tatar|Chuvash|Bashkir|Meadow Mari|Moldovan|Udmurt|Komi|Ossetian|Buryat|Kalmyk|Tuvan|Sakha|Karakalpak|Marathi|Nepali|Bihari|Maithili|Angika|Bhojpuri|Magahi|Sadri|Newari|Goan Konkani|Sanskrit|Haryanvi'''.split('|'))))


def languages():
    from ..languages import engine_language
    result={}
    for code in ['vi','en','japan','korean']+LANGUAGE_CODES:
        normalized=engine_language(code,'paddleocr')
        result.setdefault(normalized,{'code':normalized,'name':LANGUAGE_NAMES.get(code,code)})
    return list(result.values())


class PaddleOCRRecognizer:
    def __init__(self, language='vi', ocr_version='PP-OCRv5', device='cpu',
                 detection_model_dir='', recognition_model_dir=''):
        if language not in LANGUAGE_CODES:
            raise ValueError(f'PaddleOCR chưa khai báo ngôn ngữ {language}.')
        try:
            from paddleocr import PaddleOCR
        except ImportError as exc:
            raise RuntimeError('Cần cài paddleocr và paddlepaddle để sử dụng engine này.') from exc
        from ..settings import model_path
        options = {'device': device, 'use_doc_orientation_classify': False,
                   'use_doc_unwarping': False, 'use_textline_orientation': False}
        if detection_model_dir or recognition_model_dir:
            if not detection_model_dir or not recognition_model_dir:
                raise ValueError('Khi dùng model local, cần điền đủ thư mục detect và recognize PaddleOCR.')
            options.update(text_detection_model_dir=model_path(detection_model_dir),
                           text_recognition_model_dir=model_path(recognition_model_dir))
        else:
            options.update(lang=language, ocr_version=ocr_version)
        self.engine = PaddleOCR(**options)
        self.language = language

    def recognize(self, image):
        import numpy as np
        lines = []
        array = np.ascontiguousarray(np.asarray(image.convert('RGB'))[:, :, ::-1])
        for prediction in self.engine.predict(input=array):
            data = prediction if isinstance(prediction, dict) else prediction.json
            data = data.get('res', data)
            boxes = data.get('rec_polys', data.get('dt_polys', []))
            scores = data.get('rec_scores', [])
            for i, text in enumerate(data.get('rec_texts', [])):
                item = {'content': text, 'confidence': float(scores[i]) if i < len(scores) else None}
                if i < len(boxes):
                    points = np.asarray(boxes[i])
                    item['bbox_crop'] = [float(points[:,0].min()), float(points[:,1].min()),
                                         float(points[:,0].max()), float(points[:,1].max())]
                lines.append(item)
        from . import normalize_text
        return {'content': normalize_text(' '.join(line['content'] for line in lines)), 'lines': lines, 'language': self.language}
