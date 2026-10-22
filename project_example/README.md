# Dự án mẫu

Bộ dữ liệu của một lần xử lý hoàn chỉnh: 5 trang, 27 panel, kết quả OCR,
bản dịch theo ngôn ngữ, âm thanh hội thoại và video trình chiếu.

| Vị trí | Nội dung |
| --- | --- |
| `input/` | Trang gốc, ảnh/âm thanh tham chiếu, cấu hình và dữ liệu project |
| `processing/` | Trang upscale, bbox phát hiện, snapshot, frame dựng video và trạng thái trích xuất |
| `output/panels/` | Panel cắt từ trang đã upscale |
| `manifest.json` | Kết quả trích xuất, hệ tọa độ và liên kết đến artifact |
| `output/edits.json` | Timeline, thời lượng, hội thoại đã chỉnh và các bản dịch |
| `output/audio/` | Âm thanh hội thoại của lần trích xuất |
| `output/video/` | Video cuối, phụ đề ASS, thông tin dựng và clip âm thanh |
| `output/demo.mp4` | Video minh họa |

[Xem video kết quả](output/video/slideshow.mp4) · [Video minh họa](output/demo.mp4)

Đường dẫn artifact trong JSON tính từ thư mục `project_example/`.
Đây là bộ artifact để xem kết quả và nghiên cứu định dạng dữ liệu;
cấu trúc đã được sắp xếp theo công đoạn, không phải bản sao có thể chép trực tiếp vào `projects/`.

Đọc ảnh panel bằng Python, chạy từ thư mục gốc repository:

```python
import sys
sys.path.insert(0, 'src')
from manga2animation.pipeline import load_panel_images

panels = load_panel_images('project_example/manifest.json')
panels[0]['image'].show()
```

Truyền `split_panel=True` để crop lại từ ảnh upscale theo bbox trong manifest.
Ảnh giao diện phục vụ tài liệu nằm trong [`examples/docs/`](../examples/docs/).
Model weights, cache clone giọng và log chạy không nằm trong bộ mẫu.
