# Sửa trang, hội thoại và xuất MP4

## Phụ đề / transcript

Ở cột trái **Dịch/Âm → Phụ đề** (mục ngay sau Dịch), chọn bật/tắt, nguồn lời gốc
hoặc bản dịch theo ngôn ngữ, giới hạn từ/âm tiết mỗi lần hiển thị, font trên máy,
cỡ chữ, trên/giữa/dưới, căn trái/giữa/phải và khoảng cách mép ảnh.
Mặc định có thể dùng màu nhân vật nói; tắt tùy chọn này để dùng một màu chữ.
Tab **Phụ đề** bên phải cho phép ghi đè riêng từng panel.
Hộp **Tạo video → Phụ đề / transcript** cũng cho chọn các thiết lập chung trước khi xuất.

Phần chia chữ ưu tiên ranh giới câu/cụm có dấu câu trong giới hạn đã chọn,
không cắt giữa từ Latin. Câu dài hơn giới hạn vẫn cần chia thành nhiều cụm.
Tiếng Việt ước lượng âm tiết theo đơn vị cách trắng; Nhật/Trung theo ký tự.
Khi đủ clip khớp nội dung/người nói/giọng, phụ đề bám mốc từng clip đã trim,
và chia thời gian trong clip theo số âm tiết của từng cụm. Khi thiếu clip,
các câu được chia thời gian theo trọng số trên toàn thời lượng panel.
Đây là ước lượng, chưa nhận dạng mốc bắt đầu/kết thúc của từng từ trong âm thanh.

Phụ đề được đốt vào MP4 bằng FFmpeg/libass và còn có bản **ASS** tải riêng,
giữ font, căn lề và màu nhân vật. `videos/<uuid>/subtitles.json` lưu các mốc,
nguồn tính thời gian (`audio`/`estimated`) và thiết lập từng cụm để review.
Font đã chọn được chụp riêng trong thư mục video. Chọn font có glyph cho ngôn ngữ sử dụng.
Chọn nguồn dịch nhưng thiếu bản dịch sẽ bỏ qua câu đó và báo số câu thiếu sau render.

Nguồn kỹ thuật: [FFmpeg ass filter](https://ffmpeg.org/ffmpeg-filters.html#ass)
và [định dạng ASS của libass](https://github.com/libass/libass/wiki/ASS-File-Format-Guide).

## Không gian làm việc và tác vụ

Kéo đường chia giữa ba cột để đổi độ rộng; kéo đường chia trên timeline để đổi chiều cao.
Kích thước được nhớ trong trình duyệt. Có thể focus đường chia và dùng phím mũi tên.
Global prompt nằm trong tab **Cấu hình**. **Menu** trên thanh đầu chứa thao tác xóa project/Extract.
Chế độ **Bổ sung/Chạy lại toàn bộ** và nút chạy nằm ở góc trên cột trái, thay nhãn LOCAL.
Mỗi lần chạy đều lấy lại kế hoạch trang dùng lại/cần xử lý và hỏi xác nhận.
Hủy xác nhận không tạo lần Extract mới. Danh sách panel/bubble của trang dùng hàng thumbnail
gọn giống danh sách ảnh đầu vào và có thể kéo thả để đổi thứ tự.
Biểu tượng thông tin ở đầu cột phải mở metadata trong popup.

Nút **Tác vụ** mở danh sách Extract/OCR/dịch/âm thanh/video của mọi project,
hiển thị trạng thái, tiến độ, lỗi, nút dừng và áp dụng kết quả chưa ghép.
Có thể gửi thêm tác vụ khi hàng đợi đang chạy và tiếp tục biên tập.
Model GPU vẫn chạy lần lượt; OCR panel chỉ dừng được sau lần infer hiện tại.
Kết quả dịch/âm thanh của lần Extract đang mở được tự áp dụng nếu đầu vào chưa thay đổi.
Tác vụ của lần Extract khác vẫn có thể mở và áp dụng từ màn Tác vụ.

## Bản dịch theo ngôn ngữ

Dịch lưu trong `dialogue.translations[ngôn_ngữ_đích]`; trường `translation` cũ vẫn được đọc.
Chọn nhiều ngôn ngữ đích ở cấu hình dịch để tạo cùng một tác vụ.
Dropdown **Bản dịch đang xem / sửa** ở cột phải chuyển giữa các bản Việt, Anh, Nhật…
Tạo lại một bản dịch không ghi đè bản của ngôn ngữ khác.

## Sửa vùng panel/bubble

Trong Cấu hình, `upscale.scale` mặc định 2, nhận giá trị từ 1 đến 4.
Upscale toàn trang một lần; mọi bbox được chuyển theo kích thước đầu ra thực tế.
`upscale.tile` là số pixel của mảnh xử lý mỗi lượt: giảm tile để giảm VRAM,
đổi lại nhiều lượt hơn; tile không phải tỉ lệ phóng ảnh.
Đổi tỉ lệ làm mất điều kiện dùng lại kết quả xử lý cũ, nhưng không sửa/xóa lần Extract cũ.

Ngôn ngữ OCR dùng chung danh mục quốc kỳ/tên ngôn ngữ tại `data/languages.json` của source.
Tesseract chuyển `vi → vie`, `ja → jpn`, giữ `jpn_vert`; Paddle chuyển `ja → japan`,
`ko → korean`… Ngôn ngữ được chọn ở cấu hình chung hoặc khi OCR riêng panel.
Tesseract vẫn cần traineddata tương ứng trên máy. Indra/Magi hiện không có tham số ép ngôn ngữ;
UI ghi rõ phụ thuộc checkpoint, không giả vờ áp dụng lựa chọn ngôn ngữ.

Bấm một ảnh trong tab **Ảnh** để mở toàn trang. Chọn **Panel** hoặc **Bubble**:

- Bấm vùng hoặc thumbnail để chọn; kéo thân vùng để di chuyển, kéo góc để đổi kích thước.
- Nút phóng/thu hoặc Ctrl + lăn chuột để zoom; chọn bàn tay hoặc giữ nút chuột giữa để kéo ảnh.
- Kéo thumbnail ở danh sách phải hoặc dùng nút Đưa lên/xuống để đổi thứ tự panel/bubble.
  Sau khi đổi, Extract giữ thứ tự thủ công; nếu chưa đổi thì tiếp tục áp dụng hướng Nhật/Việt.
- Có thể sửa X/Y/Rộng/Cao bằng số theo pixel trang gốc.
- **Vẽ panel/bubble** cho phép kéo để tạo vùng mới. Xóa vùng chỉ thay bố cục đang sửa.
- Bubble có dropdown và nút tên màu để gán nhanh người nói, gồm Unknown.
- Vùng cắt được tự lưu trong `project.pages[].layout`. Bấm **Trích xuất** để tạo lần Extract mới áp dụng vùng đã sửa.

Khi dùng lại một trang hợp lệ, pipeline cắt lại từ ảnh upscale đã lưu, giữ ID vùng không đổi,
chỉ OCR lại vùng chữ mới/đổi bbox khi bật OCR. Chỉnh gán người nói không cần chạy lại OCR.
Vùng vẽ tay không bị bộ lọc panel nhỏ tự xóa. Các bbox ngoài panel vẫn được giữ riêng.
Manifest lần cũ không bị sửa. Panel mới nối vào timeline; panel đã bỏ khỏi bố cục không đi vào kết quả mới.
**Về panel** trở lại preview timeline. Màu nội dung thoại/bản dịch theo người nói được chọn.

## Video trình chiếu

Bấm **Tạo video** ở thanh trên, chọn độ phân giải ngang/dọc/vuông, FPS, CRF và màu nền.
Ảnh được giữ nguyên tỉ lệ, thêm nền vào phần trống. Không làm mất một phần ảnh để ép đầy khung.

- **Ghép clip lời thoại có sẵn**: phát clip theo thứ tự thoại của từng panel, chèn khoảng nghỉ từ cấu hình thời lượng.
- Clip chỉ được dùng khi còn khớp nội dung/người nói/giọng. Câu thiếu clip giữ im lặng và được thống kê.
- **Kéo dài panel** giúp phát hết lời thoại. Tắt lựa chọn này sẽ giữ thời lượng timeline và cắt phần tiếng vượt thời gian.
- Panel ẩn bị bỏ qua. Xuất video không tự gọi TTS, không gửi ảnh đến API bên ngoài.
- Có tiến độ, nút dừng, player HTML và liên kết tải MP4. Mở lại hộp thoại để chọn các video đã tạo.

Yêu cầu FFmpeg có trong PATH. Có thể dùng `imageio-ffmpeg` nếu chưa có binary hệ thống.
Video dùng H.264/AAC để phát trên trình duyệt; render FFmpeg chạy CPU để không tranh GPU với model.
Mỗi lần xuất nằm trong `projects/<id>/videos/<uuid>/`, có snapshot ảnh/clip/chỉnh sửa,
`request.json`, `status.json`, `ffmpeg.log` và `slideshow.mp4`.

```yaml
video:
  width: 1280
  height: 720
  fps: 24
  crf: 23
  include_audio: true
  extend_for_audio: true
  background: '#111111'
```

Đây là video trình chiếu; animation qua API và tự sinh kịch bản vẫn dành cho bước phát triển sau.

## Dịch và xuống dòng OCR

Một bbox chữ trả về một câu liền dòng; các dòng/độ tin cậy/tọa độ nội bộ vẫn ở metadata OCR.
Hai bbox khác nhau giữ thành hai mục thoại, không tự ghép với nhau.

Googletrans gộp nhiều câu chưa có cache thành một request có dấu phân cách ID, gửi tuần tự giữa các request,
có khoảng nghỉ `translation.request_interval` (mặc định 1 giây),
`translation.retries` (mặc định 2), backoff và tôn trọng Retry-After dạng số.
Cache SQLite ở `.cache/translations.sqlite3` tránh gửi lại cùng văn bản/source/target.
Nếu Google đổi/mất dấu phân cách, chỉ batch đó mới được dịch riêng từng câu để bảo toàn ranh giới.
Gặp 429 thì không tách batch thành nhiều request để gửi tiếp.
Khi gặp 429, các câu đã thành công được giữ; provider tạm ngừng gửi trong 60 giây.
Retry/cache không bảo đảm gỡ giới hạn bên Google;
UI hiển thị lỗi rõ ràng và giữ nguyên thoại/bản dịch cũ. [Googletrans không bảo đảm dịch vụ ổn định](https://py-googletrans.readthedocs.io/en/latest/).

## Dịch bằng LLM

Ở **Dịch/Âm → Dịch → Provider dịch**, chọn một trong ba phương án:

| Provider | Chạy ở đâu | Chuẩn bị |
| --- | --- | --- |
| Googletrans | Dịch vụ Google | Không key, có thể bị giới hạn 429 |
| Ollama local | Máy/server Ollama của bạn | Chạy Ollama và tải weight model |
| API tương thích OpenAI | Base URL được cấu hình | Model và API key theo nhà cung cấp |

Ollama gợi ý `qwen3:1.7b`, `qwen3:4b`, `qwen2.5:3b`; đây là tên gợi ý, không giới hạn lựa chọn.
`qwen3:1.7b` có bản Q4_K_M khoảng 1,4 GB theo [model card Ollama](https://ollama.com/library/qwen3:1.7b).
Cài/chạy [Ollama](https://ollama.com/download), giữ Base URL `http://127.0.0.1:11434`,
bấm **Model đã tải** để xem danh sách hoặc nhập tên model rồi **Tải model đã chọn**.
Tiến độ tải nằm trong thanh tác vụ; có thể yêu cầu dừng. Tải lại cùng model tận dụng phần Ollama đã có.
Ứng dụng không tự tải model mỗi lần dịch. Trong phạm vi các tác vụ của ứng dụng,
Ollama dùng chung khóa GPU với Extract/TTS và `keep_alive: 0` để bỏ model khỏi GPU sau yêu cầu.

Với API tương thích OpenAI, cấu hình Base URL, tên model, key hoặc tên biến môi trường key.
Ví dụ Base URL của OpenAI là `https://api.openai.com/v1`; của một server local thường có dạng
`http://127.0.0.1:<port>/v1`. Tên gợi ý `gpt-4.1-mini`, `gpt-4o-mini`, `deepseek-chat`
cần endpoint/tài khoản tương ứng; **Lấy model từ API** lấy danh sách thật qua `/models`.
Có thể nhập tên model riêng, không bắt buộc nằm trong gợi ý.
Adapter dùng [Chat Completions trong OpenAI Docs](https://developers.openai.com/api/reference/chat-completions/overview).

```powershell
$env:LLM_API_KEY = 'key-cua-ban'
python run.py
```

Giữ key trong biến môi trường khi có thể. Key nhập trực tiếp sẽ nằm trong YAML/snapshot project local;
không đưa dữ liệu project hoặc file chứa key lên Git.

Các tham số gồm số câu/batch, token đầu ra tối đa, timeout, temperature và hướng dẫn dịch thêm.
Mặc định `translation.batch_size: 16`, `max_chars_per_request: 4000`; dùng chung cho Google và LLM.
Câu quá dài được giữ riêng thay vì tự cắt đôi một bbox. `batch_requests: false` tắt gộp cho Google nếu cần.
Văn bản trùng trong cùng cấu hình được gửi một lần rồi gán về mọi ID thoại tương ứng.
LLM dùng cặp `[id,text]` và JSON gọn để giảm token; hướng dẫn được gửi một lần cho cả batch,
không gửi ảnh hoặc toàn bộ metadata panel. UI thống kê request/cache/câu trùng và token do server trả về.
Một số API dùng `max_completion_tokens` hoặc không nhận temperature; có lựa chọn riêng cho hai trường hợp này.
JSON mode chỉ bật khi endpoint hỗ trợ. LLM chỉ nhận văn bản hội thoại, không tự nhận ảnh hay suy luận người nói.
Kết quả phải có đúng ID từng câu; thiếu/nhầm ID sẽ báo lỗi và giữ dữ liệu đã chỉnh sửa.
Trong tab Dịch bên phải có thể chọn provider/model riêng cho một panel.

Kiểm thử tự động dùng endpoint giả để xác nhận giao thức HTTP, tải model, giữ ID và lưu dữ liệu.
Không gọi API trả phí trong test.
