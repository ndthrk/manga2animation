"""Giao diện chung: nhận ảnh PIL, trả content và metadata riêng của từng engine."""
from typing import Protocol, TypedDict, Any
from PIL import Image
import re


def normalize_text(text):
    """Ghép dòng trong cùng bbox; giữ nguyên ranh giới giữa các bbox khác nhau."""
    return re.sub(r'\s+', ' ', str(text or '')).strip()


class OCRResult(TypedDict, total=False):
    content: str
    lines: list[dict[str, Any]]
    timings: dict[str, Any]


class OCRRecognizer(Protocol):
    def recognize(self, image: Image.Image) -> OCRResult:
        """Đọc ảnh đã chuẩn bị, không tự upscale thêm."""
        ...
