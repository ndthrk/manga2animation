"""OCR bằng Indra ONNX; nhận cả vùng thoại và trả các dòng được phát hiện."""


class IndraOCRRecognizer:
    """Nạp model local một lần để dùng lại cho nhiều crop chữ."""

    def __init__(self, model_path, threads=4):
        import indra_ocr
        self.converter = indra_ocr.load(path=model_path, threads=threads, mode='ocr')

    def recognize(self, image):
        """Đọc ảnh PIL, giữ tọa độ từng dòng tương đối với ảnh đầu vào."""
        import numpy as np
        gray = np.asarray(image.convert('L'), dtype=np.uint8).copy()
        page = self.converter.ocr(gray)
        from . import normalize_text
        return {'content': normalize_text(page.text), 'lines': [
            {'bbox_crop': [float(v) for v in line.box], 'content': line.text,
             'confidence': float(line.conf)} for line in page.lines], 'timings': page.timings}
