# Âm thanh nhân vật và thời lượng

## Cách sử dụng

Ngôn ngữ giọng được chọn từ dropdown dùng danh mục chung
`src/manga2animation/data/languages.json`, có tên tiếng Việt, mã, bí danh và quốc kỳ đại diện.
Nếu nguồn đọc là bản dịch, chọn thêm **Đọc bản dịch ngôn ngữ** để chỉ rõ bản Việt/Anh/Nhật…
Trong cột phải, tab **Âm thanh** cho phép cấu hình riêng panel, tạo lại từng câu/toàn panel,
cắt đầu/cuối, chỉnh âm lượng và tắt tiếng từng câu khi xuất video. Chỉnh sửa không ghi đè WAV gốc.

Âm thanh **không được tạo khi Extract**. Sau khi OCR và chọn đúng người nói:

- **Tạo lại âm thanh câu**: chỉ sinh lại một câu.
- **Tạo lại âm thanh panel**: sinh mọi câu trong panel đang chọn.
- Bên trái **Dịch/Âm → Âm thanh → Tạo lại âm thanh toàn bộ**: sinh mọi câu trong panel chưa ẩn.

Mỗi câu giữ clip riêng. Tác vụ chụp lại thứ tự/câu/người nói/cấu hình; khi hoàn tất,
chỉ ghép kết quả vào các câu chưa bị sửa trong lúc đang chạy. Không thay metadata Extract gốc.
Người nói chưa nhận diện dùng **Giọng Unknown** trong tab Nhân vật; bạn có thể upload/clone giống nhân vật thường.
Nếu chưa clone giọng tương ứng, câu đó được báo lỗi riêng.
Có thể tạo lại sau khi chọn người nói đúng. Các câu thành công khác vẫn giữ kết quả.

## Batch và thiết lập

Một tác vụ nạp OmniVoice một lần cho các câu dùng cùng cấu hình; inference chia chunk theo
`audio.batch_size`, mặc định **1** cho máy hạn chế VRAM. Vẫn xuất một WAV/một câu,
không ghép văn bản nhiều nhân vật thành một giọng. Prompt của cùng người nói được dùng lại.
Đổi tốc độ (`speed`) không đổi file cũ: cần bấm tạo lại. Bbox/OCR/dịch không được chạy lại khi tạo âm thanh.

**Tạo âm thanh còn thiếu / đã đổi** bỏ qua clip còn khớp văn bản, người nói, prompt và cấu hình.
Nút **Tạo lại âm thanh toàn bộ**, panel hoặc từng câu vẫn tạo lại theo yêu cầu.
Worker giữ runtime và model ở RAM giữa các lần bấm Generate, chuyển model khỏi GPU trước khi trả kết quả.
`audio.omnivoice.keep_alive_seconds` mặc định 60; đặt 0 để giải phóng RAM ngay, tối đa 300 giây.
Không có worker âm thanh giữ VRAM khi Extract cần chạy. Đổi model/runtime hoặc dừng tác vụ sẽ đóng worker.
Preset **Nhanh · 16 bước** giảm bước sinh; preset **Chuẩn · 32 bước** giữ mặc định chất lượng.

Cấu hình chung nằm trong `audio` của YAML, tab **Dịch/Âm → Âm thanh** ở trái.
Trong tab **Thiết lập** bên phải, bật ghi đè âm thanh/thời lượng cho riêng panel.

| Trường | Ý nghĩa |
| --- | --- |
| `text_source` | Đọc thoại gốc hoặc bản dịch; chọn bản dịch cần dịch trước |
| `language` | Mã ngôn ngữ hoặc tên được OmniVoice hỗ trợ, ví dụ `vi`, `en` |
| `speed` | Hệ số tốc độ, 1 là bình thường |
| `batch_size` | Số câu mỗi lượt infer; không phải số panel/batch trên timeline |
| `num_step` | Số bước diffusion, mặc định 32 |
| `guidance_scale` | Classifier-free guidance, mặc định 2 |
| `position_temperature` / `class_temperature` | Nhiệt độ lấy mẫu theo API OmniVoice |
| `denoise` | Bật hướng dẫn khử nhiễu theo prompt |
| `preprocess_prompt` / `postprocess_output` | Tiền xử lý mẫu / hậu xử lý âm thanh |

Nguồn API/ý nghĩa tham số: [OmniVoice chính thức](https://github.com/k2-fsa/OmniVoice),
[implementation](https://github.com/k2-fsa/OmniVoice/blob/main/omnivoice/models/omnivoice.py).

## Runtime riêng, dùng Python trên máy

Magi hiện dùng Transformers 4.56, OmniVoice 0.2.1 yêu cầu Transformers >=5.3.
Worker âm thanh chạy ở tiến trình riêng, ưu tiên `vendor/omnivoice/`, không nâng cấp thư viện global.
Không cần venv hoặc cài package Manga2Animation.

Máy khác phải chọn torchaudio khớp **đúng bản torch đang dùng**. Worker còn dùng numpy,
soundfile, librosa, accelerate và dependency phụ đã có trên máy. `--no-deps` có chủ đích
để tránh pip tự nâng cấp PyTorch. Nếu máy thiếu thư viện phụ, cài riêng dependency được báo thiếu.
Có thể điền `audio.omnivoice.python_executable` và `python_path` để dùng runtime khác đã chuẩn bị.

Checkpoint không kèm repository. Tải toàn bộ [k2-fsa/OmniVoice](https://huggingface.co/k2-fsa/OmniVoice/tree/main)
vào `checkpoints/omnivoice/`, **bao gồm cả thư mục `audio_tokenizer/`**:

```text
checkpoints/omnivoice/
  config.json
  model.safetensors
  tokenizer.json
  tokenizer_config.json
  chat_template.jinja
  audio_tokenizer/
    config.json
    model.safetensors
    preprocessor_config.json
    LICENSE
```

```yaml
audio:
  batch_size: 1
  omnivoice:
    model: checkpoints/omnivoice
    device: cuda:0
    dtype: float16
```

Model sinh giọng dùng float16; bộ mã hóa âm thanh đi kèm được OmniVoice nạp trên cùng GPU
với kiểu dữ liệu mặc định của bộ mã hóa. Log `audio_worker.log` ghi thiết bị thực tế.
Extract và âm thanh dùng chung khóa GPU nên không nạp nhiều model đồng thời.
Nếu máy khác không có CUDA, đặt `device: cpu`, `dtype: float32` trong YAML của project.
UI báo thiếu checkpoint hoặc CUDA thay vì tự đổi sang CPU hay thay PyTorch.

## Thời lượng panel và batch

Ba chế độ:

- `manual`: số giây nhập tay, mặc định giữ 4 giây của pipeline hiện có.
- `text`: **min_seconds + số từ × 60 / words_per_minute**.
- `audio`: **min_seconds + tổng giây clip thực tế + (số câu − 1) × dialogue_gap**.

Việt/Latin đếm đơn vị chữ cách nhau bằng khoảng trắng; Nhật/Trung đếm từng ký tự.
Đây là ước lượng đọc, không phải đo giọng thật. Panel không có thoại vẫn có số giây tối thiểu dương.
Đổi tốc độ chung tính lại mọi panel đang kế thừa; panel ghi đè bên phải giữ cấu hình riêng.
Chế độ audio chỉ dùng clip khớp câu/người nói/giọng. Thiếu clip hoặc nội dung thay đổi
thì giữ độ dài hiện có và báo chưa đủ âm thanh, chờ tạo lại.
Timeline hiển thị giây nhỏ trên từng panel; tổng giây batch nằm trước ngữ cảnh/prompt và đầu nhóm batch,
không tính panel đã ẩn. Nút **Tạo video** ghép clip theo thứ tự thoại, giữ im lặng khi thiếu tiếng;
xem [video và sửa vùng cắt](editor.md).

## Dữ liệu

- `voice_references/*.wav`: âm thanh mẫu chuẩn hóa mono.
- `voices/<character_id>/<task_id>/prompt.pt`, `preview.wav`: prompt và nghe thử từng lần.
- `extracts/<run_id>/audio/<task_id>/*.wav`: clip từng lời thoại.
- `tasks/<task_id>/request.json`, `status.json`, `audio_worker.log`: snapshot, tiến độ và lỗi.
- `project.json`: giọng đang chọn của từng nhân vật.
- `edits.json`: đường dẫn clip, thời lượng đo được và đầu vào tạo clip của từng câu.

Chỉ nạp prompt do ứng dụng tạo ra. Model/code/codec giữ license riêng, xem `third_party/README.md`.
