"""OCR Magi v2/v3 và phần nạp model local tương thích Transformers trên máy.

Nguồn model: https://github.com/ragavsachdeva/magi
Code chính thức của model được giữ trong checkpoints, không sửa trọng số.
"""
import importlib
from pathlib import Path


def load_magi(model_path, version='v3', device='cpu', dtype='float32', processor_path=None):
    """Nạp model đã tải về, không tự tải dữ liệu hoặc thay thư viện global."""
    import torch
    from transformers import AutoConfig, AutoModel, AutoProcessor, ConditionalDetrConfig, ViTMAEConfig
    from transformers.dynamic_module_utils import get_class_from_dynamic_module
    model_path = str(Path(model_path).resolve())
    config = AutoConfig.from_pretrained(model_path, trust_remote_code=True, local_files_only=True)
    config._attn_implementation = 'eager'
    if version == 'v2':
        if processor_path is None:
            raise ValueError('Magi v2 cần đường dẫn processor TrOCR local.')
        config.ocr_pretrained_processor_path = str(Path(processor_path).resolve())
        config.detection_model_config = ConditionalDetrConfig.from_dict(config.detection_model_config.to_dict())
        config.detection_model_config.use_pretrained_backbone = False
        config.crop_embedding_model_config = ViTMAEConfig.from_dict(config.crop_embedding_model_config.to_dict())
        model = AutoModel.from_pretrained(model_path, config=config, trust_remote_code=True,
                                         local_files_only=True, torch_dtype=getattr(torch, dtype))
        processor = None
    elif version == 'v3':
        cls = get_class_from_dynamic_module('modeling_florence2.Florence2ForConditionalGeneration',
                                           model_path, local_files_only=True)
        module = importlib.import_module(cls.__module__)
        from transformers.generation import GenerationMixin
        # Transformers mới không còn tự thêm generate() cho mọi PreTrainedModel.
        language_cls = module.Florence2LanguageForConditionalGeneration
        if not issubclass(language_cls, GenerationMixin):
            class CompatibleLanguageModel(language_cls, GenerationMixin):
                """Giữ nguyên mạng và trọng số, bổ sung API sinh token của Transformers."""

                @classmethod
                def _supports_default_dynamic_cache(cls):
                    # Code Florence gốc đọc cache dạng tuple, chưa hỗ trợ DynamicCache mới.
                    return False
            module.Florence2LanguageForConditionalGeneration = CompatibleLanguageModel
        config.text_config._attn_implementation = 'eager'
        model = cls.from_pretrained(model_path, config=config, local_files_only=True,
                                    torch_dtype=getattr(torch, dtype))
        processor = AutoProcessor.from_pretrained(model_path, trust_remote_code=True, local_files_only=True)
    else:
        raise ValueError('Phiên bản Magi phải là v2 hoặc v3.')
    return model.to(device).eval(), processor


class MagiOCRRecognizer:
    """Dùng lại model đã nạp cho cả OCR và bước phân tích nhân vật."""

    def __init__(self, model, version='v3', processor=None):
        if version not in ('v2', 'v3'):
            raise ValueError('Phiên bản Magi phải là v2 hoặc v3.')
        self.model, self.version, self.processor = model, version, processor

    def recognize(self, image):
        """Đọc ảnh PIL; v3 có thể trả nhiều vùng chữ trong một ảnh."""
        import numpy as np
        import torch
        array = np.asarray(image.convert('L').convert('RGB'))
        with torch.inference_mode():
            if self.version == 'v3':
                result = self.model.predict_ocr([array], self.processor)[0]
                lines = [{'content': text, 'bbox_crop': box}
                         for text, box in zip(result['ocr_texts'], result['bboxes'])]
                from . import normalize_text
                return {'content': normalize_text(' '.join(result['ocr_texts'])), 'lines': lines}
            text = self.model.predict_ocr([array], [[[0, 0, image.width, image.height]]], batch_size=1)[0][0]
            from . import normalize_text
            return {'content': normalize_text(text), 'lines': [{'content': text, 'bbox_crop': [0, 0, image.width, image.height]}]}

    def recognize_regions(self, image, bboxes, batch_size=1, max_new_tokens=96):
        """Đọc các vùng đã detect; v2 dùng chung một lần gọi để giữ cách chia batch gốc."""
        import numpy as np
        import torch
        if self.version == 'v3':
            return [self.recognize(image.crop(box)) for box in bboxes]
        with torch.inference_mode():
            texts = self.model.predict_ocr([np.array(image.convert('RGB'))], [bboxes],
                                          batch_size=batch_size, max_new_tokens=max_new_tokens)[0]
        from . import normalize_text
        return [{'content': normalize_text(text)} for text in texts]
