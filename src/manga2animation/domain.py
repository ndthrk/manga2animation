"""Dữ liệu manifest trong bộ nhớ; ngữ cảnh đường dẫn không được ghi vào JSON."""
from pathlib import Path


class ManifestData(dict):
    def __init__(self, value, base_dir):
        super().__init__(value)
        # Giữ nơi đọc artifact ngoài nội dung JSON để project vẫn di chuyển được.
        self.base_dir = Path(base_dir).resolve()
