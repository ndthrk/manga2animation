# Kiến trúc và hợp đồng dữ liệu

## Ranh giới trách nhiệm

Real-ESRGAN xử lý toàn bộ trang ×2 rồi được giải phóng trước khi nạp Magi v2.
V2 phân tích một lần mỗi trang; hai bước hình học và đối chiếu nhân vật dùng lại kết quả.
OCR v2 dùng lại model; OCR v3/Indra/Tesseract chạy sau khi đã bỏ model phân tích.
Worker đơn và khóa file `.cache/gpu.lock` ngăn CLI/web chạy model cùng lúc.

## Manifest 1.0

- `run_id`, `created_at`, `schema_version`: định danh lần trích xuất.
- `models`: thông tin model, đường dẫn local và cấu hình đã dùng.
- `global_prompt`, `characters`: bản chụp tại thời điểm Extract.
- `pages[]`: ID nguồn ổn định, tên, thứ tự trong mảng, kích thước gốc/upscale,
  tỷ lệ thực tế, artifact và các panel.
- `panels[]`: ID từ trang/index detect, `detection_index`, thứ tự đọc `order`,
  `bbox` theo trang upscale, `coordinates` theo ba hệ tọa độ, ảnh crop, text/nhân vật.
- `texts[]`: ID, thứ tự, bbox detect/bbox padded, speaker ID, speaker instance,
  cờ essential và `ocr` chứa `status`, `engine`, `content`, metadata tùy engine.
- Nhân vật có `id` của vùng phát hiện và `character_id` của danh tính. Nhân vật đã biết
  nhận ID từ bank; chưa biết dùng `unknown_<page_id>_<cluster>` và `label: unknown`.
  Text không có liên kết cũng có ID unknown riêng, không đoán người nói.
- Vùng không gắn được panel giữ ở `unassigned_texts`/`unassigned_characters` của trang.

Mọi bbox là xyxy trong pixel, gốc trên trái, cạnh phải/dưới loại trừ.
Vùng text padded có thể vượt ranh giới panel nhưng được chặn trong trang;
tọa độ tương đối panel khi đó có thể âm. Không tự cắt mất chữ ở ranh giới panel.
Ảnh panel là PNG cắt từ trang upscale; `load_panel_images(path, split_panel=True)`
crop lại đúng vùng, không thêm upscale và không ghi ra đĩa.

## Bản chỉnh sửa và đề xuất OCR

`manifest.json`, snapshot và config lần chạy là dữ liệu gốc. Thao tác của người dùng
chỉ ghi `edits.json`: `order` giữ đủ panel ID kể cả đã ẩn, `panels[id]` lưu hidden,
duration, batch_id, prompt, dialogues. Mỗi dialogue có ID, text và speaker_id.
`batches` lưu ID/màu/context. Mặc định batch 3 panel, panel 4 giây.

Edits có `revision` tăng dần. Lưu bản cũ bị từ chối, tránh hai tab ghi đè nhau.
Ghi JSON qua file tạm rồi `os.replace`. Trình duyệt debounce khoảng 900 ms,
tuần tự hóa các lần lưu, và lưu ngay trước đổi project/extract/chạy OCR.

OCR lại lưu `proposals/<id>.json`. API áp dụng yêu cầu revision hiện tại;
giữ lựa chọn người nói đã chỉnh cho các dòng có cùng ID, thay text/danh sách theo đề xuất.
Không tự áp dụng, không sửa manifest. Người dùng cần review đề xuất trước khi bấm áp dụng.

## API

| HTTP | Đường dẫn dưới `/api` | Chức năng |
| --- | --- | --- |
| GET / POST | `/projects` | Liệt kê / tạo project |
| GET / PUT | `/projects/{pid}` | Đọc / lưu nguồn, nhân vật, prompt |
| GET / PUT | `/projects/{pid}/config` | YAML `{text: ...}` |
| POST | `/projects/{pid}/uploads?reference=false` | Multipart `files`, nhiều ảnh |
| POST | `/projects/{pid}/references/url` | Nhập ảnh tham chiếu `{url: ...}` |
| GET / POST | `/projects/{pid}/extracts` | Lịch sử / tạo job |
| POST | `/projects/{pid}/extract-plan` | Xem trước số trang dùng lại/cần xử lý |
| GET | `/projects/{pid}/extracts/{rid}` | Status, manifest và edits |
| PUT | `/projects/{pid}/extracts/{rid}/edits` | Lưu edits theo revision |
| POST | `/projects/{pid}/extracts/{rid}/ocr` | Đề xuất OCR `{panel_id, engine}` |
| GET | `/projects/{pid}/extracts/{rid}/proposals/{id}` | Tiến độ/kết quả OCR |
| POST | `/projects/{pid}/extracts/{rid}/proposals/{id}/apply` | Áp dụng với `{revision}` |
| GET | `/projects/{pid}/artifacts/{path}` | Đọc artifact trong project |
| GET | `/capabilities` | Ngôn ngữ PaddleOCR, Googletrans và provider dịch |
| DELETE | `/projects/{pid}` | Chuyển project vào thùng rác cục bộ |
| DELETE | `/projects/{pid}/extracts/{rid}` | Chuyển Extract vào thùng rác cục bộ |
| POST | `/projects/{pid}/extracts/{rid}/cancel` | Dừng giữa các lượt infer |
| POST | `/projects/{pid}/voice-uploads` | Multipart `file`, âm thanh mẫu |
| GET / POST | `/projects/{pid}/tasks` | Lịch sử / tạo tác vụ dịch, clone, nghe thử, TTS |
| GET | `/projects/{pid}/tasks/{tid}` | Trạng thái, tiến độ và kết quả riêng |
| POST | `/projects/{pid}/tasks/{tid}/apply` | Ghép kết quả chưa bị sửa, kiểm tra revision |
| POST | `/projects/{pid}/tasks/{tid}/cancel` | Yêu cầu dừng tác vụ |

UI polling tiến độ mỗi giây. Job lưu page/total/stage và lỗi/traceback nếu thất bại.
Khởi động lại đánh dấu job của tiến trình đã dừng là interrupted;
chưa resume tự động. Project sao chép được bằng cách chuyển cả thư mục project.
Đường dẫn weights trong YAML vẫn cần điều chỉnh nếu sang máy khác.

## Hướng mở rộng

OCR mới chỉ cần adapter `recognize(PIL.Image) -> dict` có `content`, đăng ký engine
trong settings và factory. Bổ sung backend detector trong ModelAdapters mà không đổi UI.
Video API tương lai nên tiêu thụ snapshot timeline đã review, giữ request/job riêng;
không nhúng vào bước OCR. MP4 trình chiếu local đã có trong `services.video`; animation qua API và sinh kịch bản chưa triển khai.

## Dịch, giọng và thời lượng

`services.enrichment` dùng cùng executor, nhưng không nằm trong Extract.
Dịch qua interface `translate(texts, source, target)`; provider gồm Googletrans 4.0.2,
Ollama `/api/chat` và API tương thích OpenAI `/chat/completions`.
LLM dùng ID nội bộ trong từng batch để khôi phục đúng thứ tự dù model đảo câu; thiếu ID không được áp dụng.
`POST /llm/models` lấy model từ endpoint; task `llm_pull` gọi Ollama `/api/pull` và lưu tiến độ.
TTS qua OmniVoice worker riêng, cùng khóa GPU với Magi. Snapshot task nằm trong `tasks/<uuid>/`.
Backend chỉ ghép kết quả khi source text, speaker, giọng và kết quả cũ vẫn khớp;
câu vừa được người dùng sửa sẽ được bỏ qua thay vì ghi đè.

`dialogue.translation` lưu text/source/target/provider/input_text;
`dialogue.audio` lưu đường dẫn WAV tương đối project, duration đo thực tế, sample_rate,
input_text/text_source/speaker_id/voice_id và cấu hình sinh.
`project.characters[].voice` lưu âm thanh mẫu, transcript, prompt tái sử dụng và preview.
`project.unknown_character` chứa màu và giọng chung cho mọi ID người nói chưa nhận diện.
Vùng artifact của voice được sao chép vào snapshot nếu nhân vật có giọng lúc Extract.

`timing`, `translation_settings`, `audio_settings` trên panel là ghi đè cấu hình chung.
Thời lượng được tính lại khi lưu và ngay trên UI khi đổi tốc độ; xem [audio.md](audio.md).
Phụ đề dùng video.subtitles và panel.subtitle_settings: chia cụm theo âm tiết/dấu câu, bám mốc clip khi đủ âm thanh và xuất ASS có màu nhân vật.

## Trích xuất bổ sung

POST Extract nhận `{mode: incremental | full, base_run_id?: uuid}`; mặc định incremental.
`extract-plan` nhận thêm `config_text` để preview YAML đang chỉnh, không ghi file.
Chọn một lần hoàn tất để kế thừa; nếu chưa chọn hoặc lần đang chọn chưa hoàn tất thì lấy lần hoàn tất gần nhất.

`services.incremental` so sánh SHA256 ảnh/ảnh tham chiếu, cấu hình xử lý, phiên bản thư viện,
mtime/kích thước checkpoint. Fingerprint không bao gồm global prompt, cấu hình dịch/TTS/thời lượng,
tên/màu nhân vật. `processing_signature`, `source_sha256`, `reused_from` trong manifest ghi nguồn dùng lại.
Kết quả trước khi có fingerprint vẫn có thể dùng lại khi kiểm tra ảnh/config/artifact và mtime model đạt yêu cầu.

`new_run` chụp `reuse.json` và sao chép artifact dưới khóa lưu trữ trước khi đưa vào queue.
Không phụ thuộc file của baseline khi worker chạy; xóa baseline sau lúc tạo job không làm hỏng lần mới.
Pipeline chỉ nạp model cho danh sách trang chưa có kết quả hợp lệ, ghép metadata theo thứ tự trang đầu vào.
Edits giữ thứ tự/batch/câu đã review và các trạng thái ẩn, thêm panel mới ở cuối với batch mới.
WAV được sao chép và đổi đường dẫn sang lần mới. Chế độ full bỏ kế thừa và tạo edits mặc định.

## Bố cục người dùng và video

`GET /projects/{pid}/pages/{page_id}/layout?run_id=...` lấy bố cục đã sửa hoặc khởi tạo từ Extract.
`project.pages[].layout` lưu bbox ở hệ tọa độ gốc, có ID panel/text ổn định và `speaker_id` từng bubble.
Pipeline ưu tiên vùng này hơn detect, cắt lại từ ảnh upscale; vùng chữ đổi được OCR lại theo engine cấu hình.
Manifest lưu `layout_override` để nhận ra trang đã áp dụng, không OCR lại vùng không đổi.

`POST /projects/{pid}/extracts/{rid}/videos` tạo snapshot render.
`GET /projects/{pid}/videos`, `GET /projects/{pid}/videos/{vid}` và `POST .../{vid}/cancel` quản lý video.
Ảnh/clip cần thiết được chụp vào thư mục `videos/<uuid>/`; FFmpeg xuất H.264/AAC,
chèn im lặng khi thiếu clip, căn thời lượng theo FPS và nối segment theo timeline.
Worker audio dùng giao thức file/JSON trên stdin, tái dùng runtime/model giữa các tác vụ;
model đợi ở CPU, chỉ chuyển lên GPU trong khóa dùng chung, tự tắt sau `keep_alive_seconds`.

## Ngôn ngữ, nhiều bản dịch và tác vụ

`GET /api/languages` đọc danh mục chung tại `src/manga2animation/data/languages.json`:
mã ngôn ngữ, tên tiếng Việt, bí danh, quốc kỳ đại diện và mã giọng của engine.
SVG quốc kỳ và MIT license nằm ở `frontend/public/flags/`.

`dialogue.translations[target]` giữ bản dịch từng ngôn ngữ. `dialogue.translation`
vẫn được giữ để tương thích dữ liệu cũ. `translation.targets` hoặc `targets` của task
cho phép dịch nhiều ngôn ngữ trong một tác vụ; các mã bí danh được chuẩn hóa để
không tạo nhiều bản Nhật với các cách viết `ja`, `jpn`, `JA`.
Áp dụng kết quả kiểm tra từng slot ngôn ngữ cùng câu nguồn, nên hai tác vụ khác ngôn ngữ
không ghi đè nhau. `audio.translation_language` chọn bản dịch để đọc và lưu vào clip;
đổi bản dịch ngôn ngữ khác không làm clip này mất hiệu lực.

`dialogue.audio_edit` lưu `start`, `end`, `volume`, `muted`; video áp dụng lúc trộn âm,
không sửa WAV gốc. Thời lượng chế độ audio tính theo đoạn đã cắt.

`GET /api/jobs` tổng hợp trạng thái từ Extract, OCR proposal, enrichment task và video
của mọi project. `POST /api/jobs/cancel` tra cứu tác vụ trước khi gửi yêu cầu dừng.
UI theo dõi các tác vụ của lần Extract đang mở, tự ghép kết quả còn khớp đầu vào,
đồng thời cho xem/áp dụng tác vụ các lần khác qua màn Tác vụ.
Hàng đợi cho phép gửi nhiều công việc; các model GPU vẫn được tuần tự hóa.

`project.pages[].layout.manual_order` / `manual_text_order` đánh dấu thứ tự vùng cắt
đã chỉnh bằng kéo thả. Chỉ override thứ tự tự động khi có cờ tương ứng;
Extract đưa thứ tự panel đã sửa vào cả manifest lẫn timeline mới.
