# Model weights

`whisper-small/`: checkpoint đa ngôn ngữ `openai/whisper-small` dùng tự chép lời âm thanh mẫu.
Revision: `973afd24965f72e36ca33b3055d56a652f456b4d`.
SHA256 trọng số: `1d7734884874f1a1513ed9aa760a4f8e97aaa02fd6d93a3a85d27b2ae9ca596b`.
Chạy trước OmniVoice rồi giải phóng bộ nhớ; không cần ASR khi đã có lời mẫu hoặc prompt giọng.

`omnivoice/`: checkpoint chính thức `k2-fsa/OmniVoice`, bao gồm `audio_tokenizer/`.
Revision đã tải: `c5fdb5ccb189668d56333f77ba2629f4cd7535f4`.
Đã đối chiếu SHA256 hai file trọng số:

- Model: `730839316de585f4c8298ec0e1712efc10fb19c6fa4e36eb741cb8d51ebcf6aa`.
- Audio tokenizer: `fe7c5e8785e0a05833e1bfc3e002ec7f55af21e306b2e7154a448c1f54ccfb0d`.

Thông tin tải nằm trong `omnivoice/download_manifest.json`; cấu hình GPU và sử dụng xem
`../docs/audio.md`. Nguồn: https://huggingface.co/k2-fsa/OmniVoice

Checkpoint dùng chung nằm tại đây; không chuyển vào lab để tránh sao chép model lớn.
Pipeline mặc định dùng `magiv2/`, `trocr-processor/` và Real-ESRGAN toàn trang ×2.
`manga_panel_detector_fp32.pt` chỉ còn dành cho POC YOLO trong lab.
Model không được tự tải khi Extract; nguồn và điều khoản xem `../third_party/README.md`.

`indra-ocr/`: bộ model ONNX v1.1.0 khớp thư viện `indra-ocr==1.1.2`, dùng cho
OCR tùy chọn trong pipeline và notebook. Gồm `det.onnx`, `rec.onnx`, `order.onnx`, `meta.json`.
`rec.onnx` hỗ trợ chữ Latin bao gồm tiếng Việt; model này đọc dòng, còn thư viện
Indra tự tách dòng khi nhận ảnh vùng thoại. File `rec.onnx` cũ ở thư mục gốc vẫn được giữ.

`magiv2/`: trọng số và code chính thức của `ragavsachdeva/magiv2`; notebook thử nghiệm
ở `lab/demo_magi.ipynb`. `trocr-processor/` chứa tokenizer và processor của
`microsoft/trocr-base-printed`; trọng số OCR đã nằm trong checkpoint Magi v2.
Checkpoint tải về đã kiểm tra SHA256:
`56392403204d3a4cca38694a3a260a6929d741869d802d6b14de35b4eab4c4b8`.
Điều khoản sử dụng model: https://huggingface.co/ragavsachdeva/magiv2#license-and-citation

`magiv3/`: Florence-2/Magi v3 chính thức, trọng số đã xác minh checksum từ Hugging Face.
Demo riêng ở `lab/demo_magi_v3.ipynb`, có thể chọn làm OCR; phân tích nhân vật vẫn dùng v2.
Nguồn và điều khoản: https://huggingface.co/ragavsachdeva/magiv3

