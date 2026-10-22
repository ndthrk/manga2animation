"""Adapter model; chỉ nạp khi công đoạn tương ứng bắt đầu."""
import gc
import os
import sys
from pathlib import Path
from ..settings import ROOT, model_path


def release_models():
    gc.collect()
    import torch
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def prepare_runtime():
    # Giữ thư viện tương thích của notebook hiện có, không nâng cấp PyTorch trên máy.
    vendor = ROOT / 'lab/vendor'
    if vendor.exists() and str(vendor) not in sys.path:
        sys.path.insert(0, str(vendor))
    os.environ.setdefault('HF_MODULES_CACHE', str(ROOT / '.cache/huggingface/modules'))


class ModelAdapters:
    def upscaler(self, cfg):
        from ..enhancement.realesrgan import RealESRGANUpscaler
        return RealESRGANUpscaler(model_path(cfg['model']), device=cfg['device'], tile=cfg['tile'])

    def magi(self, cfg, version='v2'):
        prepare_runtime()
        import torch
        from ..ocr.magi import load_magi
        torch.set_num_threads(cfg['threads'])
        return load_magi(model_path(cfg['model' if version == 'v2' else 'v3_model']),
                         version, cfg['device'], 'float16' if version == 'v3' and 'cuda' in cfg['device'] else 'float32',
                         model_path(cfg['processor']))

    def detect(self, model, image, cfg):
        import numpy as np
        import torch
        with torch.inference_mode():
            return model.predict_detections_and_associations(
                [np.array(image.convert('L').convert('RGB'))],
                **{k: v for k, v in cfg.items() if k.endswith('_threshold')})[0]

    def identify(self, model, images, predictions, characters, folder):
        import numpy as np
        import torch
        from PIL import Image
        from ..storage import safe_path
        refs = [c for c in characters if c.get('image')]
        if not refs or not any(p['characters'] for p in predictions):
            return ['Other' for p in predictions for _ in p['characters']]
        bank = {'images': [], 'names': []}
        for ref in refs:
            with Image.open(safe_path(folder, ref['image'])) as im:
                bank['images'].append(np.array(im.convert('RGB')))
            bank['names'].append(ref['id'])
        with torch.inference_mode():
            return model.assign_names_to_characters(
                [np.array(im.convert('RGB')) for im in images],
                [p['characters'] for p in predictions], bank,
                [p['character_cluster_labels'] for p in predictions])

    def recognizer(self, engine, cfg, model=None, processor=None):
        from ..languages import engine_language
        if engine == 'paddleocr':
            from ..ocr.paddle import PaddleOCRRecognizer
            options={**cfg['ocr']['paddleocr']}
            options['language']=engine_language(options['language'],engine)
            return PaddleOCRRecognizer(**options)
        if engine == 'tesseract':
            from ..ocr.tesseract import TesseractOCRRecognizer
            options={**cfg['ocr']['tesseract']}
            options['language']=engine_language(options['language'],engine)
            return TesseractOCRRecognizer(**options)
        if engine == 'indra':
            from ..ocr.indra import IndraOCRRecognizer
            return IndraOCRRecognizer(model_path(cfg['ocr']['indra']['model']), cfg['magi']['threads'])
        from ..ocr.magi import MagiOCRRecognizer
        return MagiOCRRecognizer(model, engine.replace('magi_', ''), processor)
