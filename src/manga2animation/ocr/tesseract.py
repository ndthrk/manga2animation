from PIL import ImageOps

# Tesseract cần được cài riêng; thư viện Python chỉ giúp gọi chương trình đó.


def setup_ocr(command, language):
    """Kiểm tra chương trình OCR và bộ ngôn ngữ trước khi xử lý ảnh."""
    import pytesseract
    if command:
        pytesseract.pytesseract.tesseract_cmd = command
    try:
        available = pytesseract.get_languages(config='')
    except pytesseract.TesseractNotFoundError as exc:
        raise RuntimeError('Tesseract executable not found. Install Tesseract or pass --tesseract PATH.') from exc
    missing = set(language.split('+')) - set(available)
    if missing:
        raise RuntimeError(f'Missing Tesseract language data: {sorted(missing)}. Available: {available}')
    return pytesseract


def recognize_text(engine, crop, language, psm):
    """Đọc crop đã chuẩn bị sẵn; chỉ đổi ảnh xám và thêm viền, không phóng lớn lần nữa."""
    image = ImageOps.grayscale(crop)
    image = ImageOps.expand(image, border=20, fill='white')
    raw_text = engine.image_to_string(image, lang=language, config=f'--psm {psm}', timeout=30).strip()
    from . import normalize_text
    return normalize_text(raw_text)


class TesseractOCRRecognizer:
    """Cùng giao diện nhận ảnh PIL với Indra/Magi; ảnh đã upscale ở bước chuẩn bị."""

    def __init__(self, command=None, language='vie', psm=6):
        self.engine = setup_ocr(command, language)
        self.language, self.psm = language, psm

    def recognize(self, image):
        """Chỉ đọc chữ, không tự upscale để tránh phóng lớn hai lần."""
        return {'content': recognize_text(self.engine, image, self.language, self.psm)}

