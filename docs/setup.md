# Setup nhanh trên Windows

```powershell
python run.py
```

Sau khi clone GitHub trên **máy mới**, làm theo các bước dưới đây trong thư mục dự án.

## 1. Phần mềm cần có

- Python 3.12, chọn thêm Python vào PATH khi cài.
- Node.js 22 và npm để build giao diện.
- [Tesseract](https://tesseract-ocr.github.io/tessdoc/Installation.html), cài dữ liệu `vie` cho tiếng Việt;
  thêm `eng`, `jpn`, `jpn_vert` tùy ngôn ngữ dùng.
- FFmpeg có bộ lọc `ass`/libass để xuất phụ đề. Có thể cài bản full qua
  `winget install Gyan.FFmpeg`; mở terminal mới sau khi cài.

Nếu Tesseract không ở PATH, đặt đường dẫn executable trong `ocr.tesseract.command`.
Để giữ cấu hình riêng khỏi Git, sao chép `configs/pipeline.yaml` thành
`configs/pipeline.local.yaml`, rồi sửa file local. Khi không truyền đường dẫn cấu hình,
ứng dụng ưu tiên file local nếu có. File local bị `.gitignore` loại trừ.

## 2. Cài thư viện Python

PyTorch cài riêng để chọn đúng GPU. Ví dụ cài bộ PyTorch 2.7.1 với CUDA 12.6:

```powershell
python -m pip install torch==2.7.1 torchvision==0.22.1 torchaudio==2.7.1 --index-url https://download.pytorch.org/whl/cu126
python -m pip install -r requirements.txt
```

Nếu máy đã có bộ PyTorch phù hợp thì giữ bộ hiện có. Không thêm `--upgrade`.
Các máy khác chọn bộ Torch theo [bảng chính thức](https://pytorch.org/get-started/previous-versions/).
Không có GPU thì dùng bản CPU và đặt thiết bị upscale/Magi trong YAML thành `cpu`.

`requirements.txt` là đầu mối duy nhất cho runtime chính: web, pipeline, các OCR, dịch,
đọc/ghi âm thanh và xuất video. `requirements-dev.txt` bổ sung công cụ kiểm thử.
OmniVoice có runtime riêng để tránh xung đột phiên bản Transformers.

**OmniVoice tùy chọn:** nó dùng Transformers 5.3, còn Magi dùng Transformers 4.56.
Cài thư viện âm thanh vào thư mục riêng bằng cùng Python, không đưa vào global:

```powershell
python -m pip install --target vendor/omnivoice --no-deps -r requirements-omnivoice.txt
python -m pip install --target vendor/omnivoice --no-deps torchaudio==2.7.1 --index-url https://download.pytorch.org/whl/cu126
```

Nếu đang dùng Torch khác 2.7.1, chọn torchaudio **cùng phiên bản Torch**.
Dependency thông dụng như librosa/accelerate/soundfile lấy từ runtime chính.
Không cài `requirements-omnivoice.txt` vào global cùng `requirements.txt`.

## 3. Tải model

```powershell
python scripts/download_models.py
```

Muốn clone/sinh giọng local, tải thêm OmniVoice, codec và Whisper:

```powershell
python scripts/download_models.py --audio
```

Indra/Magi v3 chỉ cần khi chọn engine tương ứng; đặt đường dẫn model trong `configs/pipeline.yaml`.
PaddleOCR có thể tải model ngôn ngữ trong lần dùng đầu; dùng thư mục local trong YAML nếu đã tải sẵn.
Ứng dụng không tự tải lại checkpoint Magi/Real-ESRGAN mỗi lần Extract.

## 4. Build UI và chạy

```powershell
npm --prefix frontend ci
npm --prefix frontend run build
python scripts/check_setup.py
python run.py
```

Mở **http://127.0.0.1:8000**. Một lệnh Python chạy backend và phục vụ frontend đã build;
không phải mở hai terminal. Lần sau chỉ cần `python run.py`.
Sau khi kéo code frontend mới từ Git, chạy lại `npm --prefix frontend run build` rồi tải lại trình duyệt.
`check_setup.py` chỉ kiểm tra, không tự cài hay thay đổi thư viện.
