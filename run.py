"""Chạy dự án bằng Python trên máy, không cần cài package hoặc đặt PYTHONPATH."""
import sys
from pathlib import Path

# Console Windows vẫn in được tiếng Việt khi chạy CLI hoặc redirect log.
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# Chỉ thêm thư mục chứa mã nguồn của dự án vào nơi Python tìm module.
sys.path.insert(0, str(Path(__file__).resolve().parent / 'src'))

from manga2animation.cli import main

if __name__ == '__main__':
    main()
