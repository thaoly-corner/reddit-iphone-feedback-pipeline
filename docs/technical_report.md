---
title: "Xây dựng nền tảng kỹ thuật dữ liệu phục vụ phân tích phản hồi khách hàng về Apple iPhone từ Reddit"
subtitle: "Báo cáo kỹ thuật — Data Engineering (CO5173), Học kỳ 1, 2026–2027"
author: "Nhóm <mã nhóm> — <Thành viên 1>, <Thành viên 2>, <Thành viên 3>, Huỳnh Thái Học"
date: "Tháng 12 năm 2026"
lang: vi
toc: true
toc-depth: 2
numbersections: true
---
\newpage

# Tổng quan đề tài

## Tên đề tài

Xây dựng một nền tảng kỹ thuật dữ liệu phục vụ phân tích phản hồi khách hàng về Apple iPhone từ Reddit, kèm ứng dụng web BrandVoice để khai thác kết quả.

## Bối cảnh nghiệp vụ

Reddit là nơi người dùng iPhone kể lại trải nghiệm thật của họ: máy nóng, pin tụt sau khi lên iOS mới, bàn phím gõ sai, camera lấy nét lệch. Riêng r/iphone trong ba tháng 5–7/2026 có khoảng 13,8 nghìn bài đăng và gần 120 nghìn bình luận. Không bộ phận nào đọc hết được lượng này bằng tay, và nếu đọc được thì cũng không trả lời được những câu hỏi kiểu "lỗi sạc tuần này tăng hay giảm so với tuần trước", "iPhone 17 Pro bị than phiền về mảng nào nhiều hơn iPhone 16 Pro".

Đề tài này xây dựng một đường ống dữ liệu đi từ kho lưu trữ Reddit dạng thô đến các bảng tổng hợp đã sẵn sàng cho phân tích, rồi dựng một ứng dụng web để bốn nhóm người dùng nghiệp vụ truy vấn các bảng đó mà không cần biết SQL hay Spark.

## Đối tượng sử dụng hệ thống

| Đối tượng                                           | Nhu cầu chính                                                                      | Trang mặc định trong ứng dụng |
| ------------------------------------------------------- | ------------------------------------------------------------------------------------ | ---------------------------------- |
| Quản lý sản phẩm (Product Manager)                  | Lỗi nào được báo nhiều nhất, lỗi nào đang tăng, xảy ra trên model nào | Issues                             |
| Chuyên viên trải nghiệm khách hàng (CX Analyst)   | Cảnh báo sớm, khiếu nại lan rộng, nhu cầu hỗ trợ                            | Emerging                           |
| Quản lý thương hiệu (Brand Manager)                | Cảm xúc cộng đồng, các cuộc thảo luận có sức lan toả                     | Sentiment                          |
| Chuyên viên phân tích marketing (Marketing Analyst) | Khác biệt giữa các model, giữa các bản iOS                                    | Compare                            |

Ứng dụng có bộ chọn vai trò ("Viewing as"); mỗi vai trò có trang mở đầu, thứ tự menu và cách gọi chỉ số riêng. Đây là cách nhóm đáp ứng tiêu chí giao diện "xét đến đặc điểm người dùng" trong rubric.

## Mục tiêu nghiệp vụ

- **BO1.** Theo dõi và tổng hợp phản hồi của người dùng iPhone từ r/iphone theo ngày, tuần, tháng.
- **BO2.** Phát hiện các vấn đề sản phẩm phổ biến hoặc đang tăng bất thường để Product Manager và CX Analyst ưu tiên điều tra.
- **BO3.** Cung cấp cảm xúc người dùng, nhận xét theo tính năng, xu hướng khiếu nại, mức độ tương tác, nhu cầu hỗ trợ cho hoạt động quản lý sản phẩm, thương hiệu và marketing.

## Phạm vi

- Nguồn dữ liệu: bài đăng (submissions) của r/iphone từ Academic Torrents, ba tháng 5, 6, 7 năm 2026. Bình luận chỉ dùng số lượng (`num_comments`), không xử lý nội dung bình luận.
- Ngôn ngữ: tiếng Anh. Taxonomy có một số từ khoá tiếng Việt nhưng dữ liệu thực tế gần như không có.
- Xử lý theo lô là luồng chính. Phần streaming (PRAW → Kafka) được cài đặt dưới dạng producer và bộ máy phát hiện bất thường theo cửa sổ trượt, chưa vận hành liên tục.

# Yêu cầu nghiệp vụ

Nhóm có bốn thành viên, đề bài yêu cầu tối thiểu $2n = 8$ yêu cầu nghiệp vụ. Nhóm định nghĩa tám yêu cầu chính (BR01–BR08) bám theo ba mục tiêu nghiệp vụ ở mục 1.4, và thêm hai yêu cầu mở rộng (BR09, BR10) khai thác hai đặc điểm của dữ liệu: ba tháng liên tiếp cho phép xét mức độ tái diễn của lỗi theo tháng, và một phần lớn bài đăng trên r/iphone là câu hỏi nhờ giúp đỡ nên có thể đo nhu cầu hỗ trợ theo chủ đề.

Mỗi yêu cầu dưới đây được ánh xạ tới một bảng Gold, một nhóm endpoint của API và một trang trong ứng dụng. Bảng tổng hợp ở mục 6.3.

## BR01 — Theo dõi khối lượng phản hồi khách hàng

- **Đối tượng:** Product Manager, CX Analyst.
- **Câu hỏi:** Số bài đăng và bình luận về iPhone thay đổi thế nào theo ngày, tuần, tháng? Ngày nào thảo luận nhiều nhất và vì sao?
- **Kết quả:** chuỗi số bài/bình luận theo ngày; tổng theo tuần kèm tăng trưởng tuần-trên-tuần; các ngày cao điểm, mỗi ngày đi kèm bài đăng tiêu cực có tương tác cao nhất của ngày đó để giải thích đỉnh.
- **Gold:** `feedback_volume`. **API:** `/volume/daily`, `/volume/weekly`, `/volume/summary`, `/volume/peaks`. **Trang:** Overview.

## BR02 — Xác định các vấn đề sản phẩm phổ biến

- **Đối tượng:** Product Manager.
- **Câu hỏi:** Những lỗi nào được phản ánh nhiều nhất? Chiếm bao nhiêu phần trăm tổng phản hồi lỗi?
- **Kết quả:** bảng xếp hạng 11 nhóm lỗi theo số bài, tỷ trọng trên tổng lỗi, tỷ lệ tiêu cực, tương tác trung bình, đường xu hướng tuần; khoan sâu từng lỗi theo model và theo bản iOS.
- **Gold:** `issue_summary`. **API:** `/issues/ranking`, `/issues/detail`. **Trang:** Issues.

Taxonomy lỗi gồm 6 nhóm tính năng và 11 loại lỗi kỹ thuật (bảng 4.2), cộng một nhãn "Non-Defect / General Inquiry" cho bài không thuộc lỗi nào.

## BR03 — Phát hiện vấn đề mới nổi

- **Đối tượng:** Product Manager, CX Analyst.
- **Câu hỏi:** Có lỗi nào đang tăng đột biến trong vài ngày gần đây so với mức nền của chính nó không?
- **Kết quả:** danh sách cảnh báo theo ngày × model × lỗi với số bài trung bình 3 ngày, mức nền 14 ngày, tốc độ tăng, z-score, mức cảnh báo; người dùng có thể nới hoặc siết ngưỡng ngay trên giao diện.
- **Gold:** `emerging_issues`. **API:** `/emerging/alerts`, `/emerging/series`, `/emerging/heatmap`. **Trang:** Emerging.

## BR04 — Phân tích cảm xúc khách hàng

- **Đối tượng:** Brand Manager, CX Analyst.
- **Câu hỏi:** Người dùng đang tích cực, tiêu cực hay trung lập? Cảm xúc thay đổi ra sao theo thời gian, theo lỗi, theo model?
- **Kết quả:** tỷ lệ ba lớp cảm xúc theo ngày/tuần; net sentiment (tích cực trừ tiêu cực); phân rã theo lỗi và theo model.
- **Gold:** `sentiment_summary` (và `issue_summary` khi lọc theo lỗi/iOS). **API:** `/sentiment/timeline`, `/sentiment/by-issue`, `/sentiment/by-model`. **Trang:** Sentiment.

## BR05 — Phân tích phản hồi theo tính năng

- **Đối tượng:** Product Manager.
- **Câu hỏi:** Pin, camera, màn hình, hiệu năng, kết nối được đánh giá thế nào?
- **Kết quả:** số lượt nhắc, số tích cực/tiêu cực, tỷ lệ tiêu cực, tương tác trung bình cho từng cặp tính năng × lỗi; biểu đồ phân tán khối lượng – độ tiêu cực; chỉ số "complaint load" = số bài tiêu cực × tương tác trung bình.
- **Gold:** `feature_feedback`. **API:** `/features/matrix`. **Trang:** Features.

## BR06 — Xác định các khiếu nại có mức độ ảnh hưởng cao

- **Đối tượng:** Brand Manager, CX Analyst.
- **Câu hỏi:** Khiếu nại nào đang được cộng đồng chú ý nhất?
- **Kết quả:** danh sách bài tiêu cực xếp theo chỉ số tác động, có điểm Reddit, số bình luận, điểm tương tác, đường dẫn về bài gốc; tổng tương tác theo nhóm lỗi.
- **Gold:** `high_impact_complaints`. **API:** `/complaints`. **Trang:** Complaints.

## BR07 — Theo dõi xu hướng các vấn đề

- **Đối tượng:** Product Manager.
- **Câu hỏi:** Khiếu nại về pin, nhiệt, kết nối đang tăng hay giảm?
- **Kết quả:** chuỗi tuần cho từng lỗi, thay đổi tuần-trên-tuần, hệ số góc hồi quy tuyến tính (bài/tuần) để nói "tăng" hay "giảm" không chỉ dựa vào hai tuần cuối.
- **Gold:** `issue_trends`. **API:** `/issues/trends`. **Trang:** Issues (phần Weekly trajectories).

## BR08 — So sánh phản hồi giữa các model iPhone hoặc phiên bản iOS

- **Đối tượng:** Product Manager, Marketing Analyst.
- **Câu hỏi:** Các model khác nhau ở điểm gì? Phản hồi khác nhau thế nào giữa iOS 18 và iOS 26?
- **Kết quả:** so sánh tối đa bốn model hoặc bốn bản iOS lớn về số phản hồi, tỷ lệ tiêu cực, cảm xúc trung bình, tương tác, phân bố theo tính năng; biểu đồ toàn cảnh mọi model.
- **Gold:** `model_comparison`. **API:** `/compare/options`, `/compare/models`, `/compare/ios`, `/compare/generations`. **Trang:** Compare.

## BR09 (mở rộng) — Theo dõi vấn đề tái diễn theo tháng

- **Đối tượng:** Product Manager, CX Analyst.
- **Câu hỏi:** Lỗi nào xuất hiện lặp lại ở nhiều tháng, lỗi nào chỉ bùng lên một lần?
- **Kết quả:** ma trận lỗi × tháng; số tháng có mặt; cờ tái diễn khi có mặt từ hai tháng trở lên; độ biến động giữa các tháng.
- **Gold:** `recurring_issues`. **API:** `/recurring`. **Trang:** Support.

## BR10 (mở rộng) — Phân tích nhu cầu hỗ trợ

- **Đối tượng:** CX Analyst, Marketing Analyst.
- **Câu hỏi:** Người dùng hỏi giúp đỡ về chủ đề gì, trên model nào, xu hướng theo tháng ra sao?
- **Kết quả:** số câu hỏi theo 9 nhóm hỗ trợ × tháng × model × iOS; tỷ trọng từng nhóm; thay đổi tháng-trên-tháng; model nào hỏi nhiều nhất và hỏi về gì.
- **Gold:** `support_demand`. **API:** `/support/demand`. **Trang:** Support.

# Nguồn dữ liệu

## Nguồn dữ liệu lịch sử

Nguồn chính là bộ lưu trữ Reddit trên Academic Torrents (magnet `E04A4FDA…`), gồm các tệp `RS_YYYY-MM.zst` (submissions) và `RC_YYYY-MM.zst` (comments) nén bằng Zstandard. Nhóm dùng ba tệp `RS_2026-05`, `RS_2026-06`, `RS_2026-07`.

Mỗi tệp chứa toàn bộ bài đăng của Reddit trong tháng, không chỉ r/iphone. Ví dụ tháng 7/2026: bộ lọc duyệt khoảng 45,7 triệu bản ghi để giữ lại 4 205 bài của r/iphone, tức dưới 0,01%. Vì vậy bước giải nén và lọc được viết theo kiểu streaming (đọc từng dòng JSON từ luồng giải nén, `max_window_size = 2^31`) thay vì giải nén cả tệp ra đĩa; Colab không đủ dung lượng cho cách thứ hai.

Tải xuống dùng `aria2c --select-file` để chỉ lấy đúng một tệp trong torrent. Tệp JSONL đã lọc của tháng 7 nặng 18,0 MB; sau khi chuyển sang Parquet Snappy còn 3,37 MB.

## Nguồn dữ liệu tăng dần

Bài đăng mới được lấy qua Reddit API bằng thư viện PRAW và đẩy vào Apache Kafka (topic `reddit.posts.raw`, khoá phân vùng là tên subreddit, nén Snappy, `acks=all`). Repository có hai producer: `kafka_praw_producer.py` đọc từ API thật và `replay_producer.py` phát lại dữ liệu Bronze để kiểm thử mà không cần khoá API. Phần này phục vụ minh hoạ luồng thu thập liên tục và benchmark bộ máy phát hiện bất thường; dữ liệu trong báo cáo này hoàn toàn đến từ nguồn lịch sử.

## Lược đồ dữ liệu bài đăng

Một bản ghi submission của Reddit có 121 trường. Nhóm giữ nguyên toàn bộ ở tầng Bronze và chỉ dùng các trường sau ở tầng Silver:

| Thuộc tính                                  | Ý nghĩa                                                                 |
| --------------------------------------------- | ------------------------------------------------------------------------- |
| `id`                                        | Mã bài đăng, khoá khử trùng lặp                                   |
| `subreddit`                                 | Cộng đồng, luôn là `iphone` sau khi lọc                           |
| `author`                                    | Tác giả; `[deleted]` nếu tài khoản đã xoá                       |
| `title`                                     | Tiêu đề                                                                |
| `selftext`                                  | Nội dung; có thể là `[removed]`, `[deleted]` hoặc rỗng          |
| `crosspost_parent_list`                     | Danh sách bài gốc nếu là crosspost; dùng để khôi phục nội dung |
| `created_utc`                               | Thời điểm đăng (epoch giây)                                         |
| `score`, `num_comments`, `upvote_ratio` | Điểm, số bình luận, tỷ lệ upvote                                   |
| `permalink`                                 | Đường dẫn tương đối về bài trên Reddit                         |
| `_meta`                                     | Metadata của bộ lưu trữ: bài có bị gỡ sau đó không, bởi ai    |

## Lược đồ dữ liệu bình luận

Tệp `RC_*` có các trường `id`, `link_id`, `parent_id`, `author`, `body`, `created_utc`, `score`, `subreddit`. Nhóm chưa xử lý nội dung bình luận; số bình luận của mỗi bài lấy từ `num_comments` của submission.

## Đặc trưng dữ liệu

Profiling tháng 7/2026 (4 205 bài, chạy bằng `ingestion/historical/profiling/data_profiler.py`):

| Chỉ số                                                 | Giá trị                                                                      |
| -------------------------------------------------------- | ------------------------------------------------------------------------------ |
| Số bài, số tác giả                                  | 4 205 bài, 3 724 tác giả, 0 trùng `id`                                   |
| `selftext` bị gỡ bởi mod (`[removed]`)            | 839 bài (19,9%)                                                               |
| `selftext` bị tác giả xoá (`[deleted]`)          | 17 bài (0,4%)                                                                 |
| `selftext` rỗng (bài chỉ có tiêu đề hoặc ảnh) | 674 bài (16,0%)                                                               |
| `score`: trung bình / trung vị / lớn nhất          | 15,0 / 1 / 2 894                                                               |
| `num_comments`: trung bình / trung vị / lớn nhất   | 8,7 / 2 / 1 456                                                                |
| `upvote_ratio` trung bình                             | 0,675                                                                          |
| Độ dài tiêu đề trung bình                         | 46 ký tự                                                                     |
| Độ dài nội dung: trung bình / lớn nhất            | 293 / 16 006 ký tự                                                           |
| Số bài mỗi ngày                                      | 110–164                                                                       |
| Trường có 100% giá trị thiếu                       | `approved_by`, `banned_by`, `category`, … (phần lớn là trường mod) |

Những đặc trưng này quyết định một số lựa chọn thiết kế:

- **Volume.** Ba tháng chỉ 13 959 bài sau lọc, nhưng để có 13 959 bài đó phải đọc hơn 130 triệu bản ghi nén. Chi phí nằm ở ingestion, không nằm ở xử lý.
- **Velocity.** r/iphone có 110–180 bài/ngày, đủ để nhìn tăng trưởng theo ngày nhưng số bài cho một cặp (model, lỗi) trong một ngày thường chỉ 1–3. Ngưỡng cảnh báo của BR03 vì thế phải có điều kiện "trung bình 3 ngày ≥ 2" để tránh cảnh báo trên một bài lẻ.
- **Variety.** Metadata có cấu trúc (điểm, thời gian) đi cùng văn bản tự do. Taxonomy lỗi và model chạy trên văn bản; tương tác và thời gian chạy trên metadata.
- **Data quality.** Khoảng 36% bài không còn nội dung (gỡ, xoá, rỗng); 400 bài được khôi phục từ `crosspost_parent_list`. Điểm `score` lệch phải rất mạnh (trung vị 1, lớn nhất 2 894) nên chỉ số tác động dùng thang log.

## Các thuộc tính sau quá trình làm giàu dữ liệu

| Thuộc tính                             | Cách sinh                                                                      | Phủ trên dữ liệu thật                              |
| ---------------------------------------- | ------------------------------------------------------------------------------- | ------------------------------------------------------- |
| `iphone_model`                         | Regex `iphone (3–17 \| x \| xr \| xs \| se)(pro max \| pro \| plus \| mini \| air)?` | 33% bài có model                                      |
| `ios_version`                          | Regex `ios (15–28)(.x)*( beta)?`                                             | 8% bài có phiên bản                                 |
| `feature_category`, `issue_category` | Khớp từ khoá taxonomy trên tiêu đề + nội dung                           | 24% bài là lỗi kỹ thuật, 76% là thảo luận chung |
| `sentiment`, `sentiment_score`       | RoBERTa `cardiffnlp/twitter-roberta-base-sentiment-latest`                    | 100%; NEG 44,4%, NEU 46,1%, POS 9,5%                    |
| `is_question`, `support_category`    | Regex dấu hỏi / "how do i" / "why does" … và 8 nhóm hỗ trợ               | 65% bài là câu hỏi                                  |
| `engagement_score`                     | $score + 2 \times num\_comments$                                              | 100%                                                    |
| `impact_index`                         | $\ln(1 + \max(0, engagement)) \times (0.5 + 0.5 \times upvote\_ratio)$        | 100%                                                    |

Ví dụ, bài "Why on my iphone 17 the back cover can be slipped with paper?" (tháng 7/2026) trở thành: `iphone_model = iPhone 17`, `feature_category = Chassis & Build Quality`, `issue_category = Back Cover & Seal Defect`, `sentiment = NEGATIVE`, `is_question = true`, `support_category = Other Support`.

# Giải pháp kỹ thuật dữ liệu

## Kiến trúc tổng thể

Nhóm dùng kiến trúc Medallion ba tầng Bronze → Silver → Gold trên kho đối tượng, cộng một tầng Serving quan hệ cho ứng dụng.

```
Academic Torrents (.zst)          Reddit API (PRAW)
        │                                │
        │ zstandard streaming filter     │ Kafka producer
        ▼                                ▼
   Bronze  ── s3://<bucket>/bronze/posts/year=2026/month=05..07   (Parquet Snappy, SHA-256)
        │
        │ PySpark: dedupe, khôi phục crosspost, regex, taxonomy, RoBERTa UDF
        ▼
   Silver  ── s3://<bucket>/silver/posts/feedback_year=/feedback_month=
        │
        │ Spark SQL (batch)  +  stateful sliding window (BR03)
        ▼
   Gold    ── s3://<bucket>/gold/<10 mart>
        │
        │ SQLAlchemy idempotent sync
        ▼
   Serving ── AWS RDS PostgreSQL 18: galaxy schema + gold_* snapshots
        │
        ▼
   BrandVoice ── FastAPI /api/v1 → React + ECharts
```

Toàn bộ pipeline chạy trên Google Colab (GPU T4 cho RoBERTa) với mã nguồn trong repository; mỗi tầng là một module độc lập có thể chạy bằng `python -m scripts.run_pipeline --stage {silver|gold|serving}`.

## Tầng Bronze

`ingestion/historical/` thực hiện bốn việc cho mỗi tháng:

1. Tìm và tải đúng tệp `RS_YYYY-MM.zst` trong torrent (`torrent_downloader.py`).
2. Giải nén theo luồng, lọc `subreddit == "iphone"`, ghi JSONL (`bronze_zst_ingestor.py`).
3. Profiling thống kê: tỷ lệ thiếu, bài bị gỡ, phân phối số, số bài theo ngày (`data_profiler.py`).
4. Tuần tự hoá các trường lồng nhau (`_meta`, `crosspost_parent_list`, `all_awardings`) thành chuỗi JSON, thêm cột kiểm toán `_ingest_source`, `_ingest_period`, `_ingest_scope`, `_ingested_at_utc`, ghi Parquet Snappy phân vùng `year=/month=` và tính SHA-256 của tệp.

Bronze giữ nguyên 121 trường gốc. Không sửa, không lọc nội dung ở tầng này để Silver có thể chạy lại với taxonomy khác mà không cần tải lại torrent.

Kết quả: 13 959 bài cho ba tháng.

## Tầng Silver

`processing/batch/bronze_to_silver/spark_cleaner.py` và `processing/batch/enrichment/silver_enrichment.py` chạy trên PySpark:

- **Khử trùng lặp** theo `id`, giữ bản ghi có `created_utc` mới nhất: loại 147 bài (1,05%).
- **Khôi phục nội dung**: nếu `selftext` là `[removed]`, `[deleted]` hoặc rỗng mà có `crosspost_parent_list`, lấy `selftext` của bài gốc. Khoảng 400 bài được khôi phục.
- **Làm sạch văn bản**: bỏ URL, HTML entity, markdown; ghép tiêu đề và nội dung thành `clean_text`.
- **Trích xuất thực thể** model iPhone và phiên bản iOS bằng regex trong `DomainTaxonomyConfig`.
- **Phân loại lỗi** theo bảng từ khoá:

| Nhóm tính năng       | Loại lỗi               | Ví dụ từ khoá                             |
| ----------------------- | ------------------------ | --------------------------------------------- |
| Battery & Thermal       | Rapid Battery Drain      | battery drain, battery life, battery health   |
| Battery & Thermal       | Thermal Overheating      | overheat, gets hot, running hot               |
| Battery & Thermal       | Charging Failure         | won't charge, magsafe, charging port          |
| Chassis & Build Quality | Structural Bending       | bend, bent, bendgate                          |
| Chassis & Build Quality | Back Cover & Seal Defect | back glass, slipped with paper                |
| Display & Touch         | Screen Artifacts         | green line, flicker, burn-in, dead pixel      |
| Display & Touch         | Touch & Keyboard Lag     | typos, swipe typing, ghost touch              |
| Camera & Optics         | Focus & Exposure Bug     | focus point, exposure, blurry, camera control |
| Connectivity & Network  | Wireless & Cellular Drop | wifi drop, no service, bluetooth, carplay     |
| OS & System Software    | UI Lag & System Freeze   | lag, stutter, freeze, bootloop, crash         |
| OS & System Software    | Search & Settings Bug    | settings search, spotlight, storage, icloud   |

- **Cảm xúc**: mô hình RoBERTa chạy trong Arrow pandas UDF, batch 32, trên GPU. Nhãn `POSITIVE/NEUTRAL/NEGATIVE` và điểm có dấu trong $[-1, 1]$. Nếu không tải được mô hình, UDF rơi về bộ từ điển (lexicon) để pipeline không dừng.
- **Câu hỏi và nhóm hỗ trợ**: `is_question` bắt dấu `?` và các cụm "how do i", "how to", "why does", "need help"…; `support_category` chỉ gán khi `is_question = true`, dựa trên 8 nhóm từ khoá (Battery & Charging, Connectivity, Camera & Photos, Display & Touch, iOS & Settings, Storage & iCloud, Data Transfer & Migration, Account & Apple ID), còn lại là Other Support.
- **Tương tác**: `engagement_score`, `impact_index` theo công thức ở mục 3.6.
- **Thời gian**: `created_datetime`, `feedback_date`, `feedback_year`, `feedback_month`.

Silver ghi Parquet phân vùng theo `feedback_year`, `feedback_month`, chế độ overwrite. Kết quả 13 812 bài: tháng 5 có 5 043, tháng 6 có 4 606, tháng 7 có 4 163.

## Tầng Gold

`processing/batch/silver_to_gold/gold_datamarts.py` sinh mười mart. Bảng dưới liệt kê grain và công thức đáng chú ý; số dòng là của lần chạy ngày 29/10/2026.

| Mart                       | BR   | Grain                                            | Số dòng | Ghi chú                                                |
| -------------------------- | ---- | ------------------------------------------------ | --------- | ------------------------------------------------------- |
| `feedback_volume`        | BR01 | ngày × tuần × subreddit                      | 92        | `total_discussion_units = posts + comments`           |
| `issue_summary`          | BR02 | ngày × model × iOS × tính năng × lỗi     | 4 272     | đếm pos/neu/neg, trung bình sentiment và engagement |
| `emerging_issues`        | BR03 | ngày × model × tính năng × lỗi            | 2 056     | 112 dòng `is_anomaly = true`                         |
| `sentiment_summary`      | BR04 | ngày × model × sentiment                      | 3 138     |                                                         |
| `feature_feedback`       | BR05 | tính năng × lỗi                              | 12        | `negative_ratio_pct`                                  |
| `high_impact_complaints` | BR06 | bài                                             | 500       | top 500 bài NEGATIVE theo engagement                   |
| `issue_trends`           | BR07 | tuần × tính năng × lỗi                     | 162       | `wow_growth_pct` qua `lag()`                        |
| `model_comparison`       | BR08 | model × iOS × tính năng                      | 771       | `defect_complaint_rate_pct`                           |
| `recurring_issues`       | BR09 | lỗi × năm × tháng                           | 33        | `is_recurring = active_period_count >= 2`             |
| `support_demand`         | BR10 | nhóm hỗ trợ × năm × tháng × model × iOS | 1 185     | chỉ `is_question = true`                             |

Quy tắc phát hiện bất thường của BR03, tính cho từng khoá (model, tính năng, lỗi) theo ngày $t$:

$$
curr_{3d} = \overline{v}_{[t-2,\,t]},\qquad base_{14d} = \overline{v}_{[t-16,\,t-3]},\qquad \sigma = \max(\mathrm{std}(v_{[t-16,\,t-3]}),\,0.5)
$$

$$
growth = \frac{curr_{3d} - base_{14d}}{\max(base_{14d}, 1)} \times 100,\qquad z = \frac{curr_{3d} - base_{14d}}{\sigma}
$$

$$
is\_anomaly = (curr_{3d} \ge 2) \land (growth \ge 150 \lor z \ge 2)
$$

Sàn $\sigma = 0.5$ tránh chia cho 0 khi mức nền phẳng; điều kiện $curr_{3d} \ge 2$ loại các khoá chỉ có một bài.

Phần tính BR03 có thể chạy bằng một trong ba bộ máy (mục 4.7). Các mart còn lại dùng Spark SQL.

## Tầng Serving

`serving/database/postgres_loader.py` đồng bộ Gold vào PostgreSQL theo hai dạng:

1. **Bản sao `gold_*`**: mỗi mart thành một bảng cùng tên có tiền tố `gold_`, thay thế trong một giao dịch và kiểm tra số dòng sau khi ghi. Ứng dụng đọc các bảng này.
2. **Mô hình chiều**: bốn chiều dùng chung `dim_date` (92), `dim_iphone_model` (98), `dim_os_version` (64), `dim_issue_category` (12) và ba bảng sự kiện `fact_feedback_summary` (4 272), `fact_emerging_issues` (2 056), `fact_high_impact_complaints` (500) theo mô hình **galaxy** (fact constellation). Nạp bằng `INSERT … ON CONFLICT DO UPDATE` nên chạy lại không sinh trùng.

Cùng một bộ nạp còn sinh thêm phiên bản star, snowflake (3NF với `snow_dim_model_series`, `snow_dim_feature_group`) và one-big-table (`obt_feedback_wide`) để benchmark bốn mô hình lược đồ. Chỉ mục: B-tree ghép `(date_key, model_id)` trên fact, chỉ mục một phần `WHERE is_anomaly = TRUE` trên `fact_emerging_issues`, chỉ mục giảm dần trên `engagement_score`.

Cơ sở dữ liệu thật là AWS RDS for PostgreSQL 18 (ap-southeast-1), kết nối SSL. Cấu hình SQLite cục bộ dùng cho phát triển và kiểm thử đơn vị.

## Công nghệ sử dụng

| Thành phần                | Công nghệ                                                                           | Vai trò trong hệ thống                     |
| --------------------------- | ------------------------------------------------------------------------------------- | --------------------------------------------- |
| Nguồn lịch sử            | Academic Torrents + aria2                                                             | Tải tệp `RS_*.zst` theo tháng            |
| Giải nén, lọc            | Python `zstandard`                                                                  | Đọc luồng JSONL không giải nén ra đĩa |
| Thu thập tăng dần        | Python, PRAW, Apache Kafka (`kafka-python`)                                         | Producer bài đăng mới                     |
| Data lake                   | AWS S3 (có cấu hình MinIO thay thế)                                               | Bronze, Silver, Gold                          |
| Định dạng                | Apache Parquet, nén Snappy                                                           | Lưu cột, phân vùng theo thời gian        |
| Xử lý lô                 | Apache Spark 3 / PySpark, Spark SQL                                                   | Silver và Gold                               |
| NLP                         | Hugging Face Transformers, PyTorch, Arrow pandas UDF                                  | Sentiment RoBERTa phân tán trong Spark      |
| Xử lý luồng (BR03)       | Bộ máy cửa sổ trượt có trạng thái; Spark Structured Streaming; Kafka Streams | Phát hiện bất thường                     |
| Cơ sở dữ liệu phục vụ | AWS RDS for PostgreSQL 18, SQLAlchemy                                                 | Galaxy schema + snapshot Gold                 |
| Backend                     | FastAPI, pandas, psycopg2                                                             | REST API `/api/v1`                          |
| Frontend                    | React 19, TypeScript, Vite, ECharts, TanStack Query, Tailwind v4                      | Giao diện BrandVoice                         |
| Triển khai                 | Docker Compose (api + nginx)                                                          | Chạy ứng dụng bằng một lệnh             |
| Môi trường xử lý       | Google Colab (T4)                                                                     | Chạy pipeline                                |
| Mã nguồn                  | Git, GitHub                                                                           | Cộng tác                                    |

## Giải pháp thay thế và cấu hình pluggable

Để so sánh công nghệ, mỗi giai đoạn có một lựa chọn chính và ít nhất một lựa chọn thay thế, chọn qua `PipelineExecutionConfig` trong `config/pipeline_config.py`:

| Giai đoạn  | Chính              | Thay thế                                                                                                                                         | Tiêu chí đo                                               |
| ------------ | ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------ |
| Silver (NLP) | `pyspark_roberta` | `pyspark_lexicon` (từ điển có xử lý phủ định), `hadoop_mapreduce_silver` (RDD map/reduceByKey/flatMap), `duckdb_vectorized_silver` | độ trễ, thông lượng, RAM đỉnh, độ sâu ngữ nghĩa |
| Gold batch   | `spark_sql`       | `hadoop_mapreduce`, `duckdb_biglake` (SQL serverless trên Parquet)                                                                           | độ trễ, RAM đỉnh, số nhóm đầu ra                    |
| Stream BR03  | `apache_flink`    | `spark_streaming`, `kafka_streams`                                                                                                            | sự kiện/giây, độ trễ, bộ nhớ trạng thái            |
| Serving      | `postgres`        | `sqlite_local`, `duckdb_biglake`, `hive_metastore`                                                                                          | dung lượng, RAM, độ trễ truy vấn P50/P95/P99           |
| Lược đồ  | `galaxy`          | `star`, `snowflake`, `obt`                                                                                                                  | số join, mức chuẩn hoá, dung lượng, độ trễ          |

Một điểm cần nói rõ: bộ máy gắn nhãn `apache_flink` và `kafka_streams` trong repository là cài đặt Python của thuật toán cửa sổ trượt có trạng thái theo khoá (deque giữ 17 ngày gần nhất cho mỗi khoá), mô phỏng ngữ nghĩa keyed state của Flink và KTable của Kafka Streams; nhóm không triển khai cụm Flink hay ứng dụng Kafka Streams thật. `spark_streaming` dùng cửa sổ `rangeBetween` của Spark trên cùng dữ liệu. Ba bộ máy cho kết quả giống nhau trên `emerging_issues`, khác nhau ở cách giữ trạng thái và chi phí.

Cấu hình được chọn làm luồng chính sau benchmark (mục 6.2): `pyspark_roberta / spark_sql / apache_flink / postgres / galaxy`.

## Quy trình thực hiện

| Giai đoạn                | Việc đã làm                                                                 | Sản phẩm                                                  |
| -------------------------- | ------------------------------------------------------------------------------- | ----------------------------------------------------------- |
| 1. Phân tích nghiệp vụ | Xác định 4 nhóm người dùng, 3 mục tiêu, 8 BR ban đầu, sau đó 10 BR | `docs/data/business_requirements.md`, mục 2              |
| 2. Khảo sát dữ liệu    | Tải thử tháng 7, profiling 121 trường, đo tỷ lệ bài bị gỡ            | `notebooks/historical_posts.ipynb`, mục 3.5              |
| 3. Thiết kế kiến trúc  | Medallion + galaxy, cấu hình pluggable                                        | `docs/architecture/architecture.md`                       |
| 4. Thu thập               | Ingest ba tháng, upload S3                                                     | `ingestion/historical/`, `notebooks/DE_ingestion.ipynb` |
| 5. Xử lý, làm giàu     | Silver trên Colab T4                                                           | `processing/`, `nlp/`                                   |
| 6. Lưu trữ, phục vụ    | Gold 10 mart, nạp RDS                                                          | `serving/database/`                                       |
| 7. Ứng dụng              | BrandVoice                                                                      | `application/`                                            |
| 8. Đánh giá             | Kiểm tra đối chiếu, benchmark, latency                                      | mục 6                                                      |

# Ứng dụng BrandVoice

## Kiến trúc ứng dụng

```
application/
├── api/            FastAPI, Python 3.12
│   └── app/
│       ├── main.py         khởi tạo, CORS, middleware đo thời gian
│       ├── config.py       đọc DB_* từ .env dùng chung với pipeline
│       ├── db.py           SQLAlchemy engine, query_df(), cache TTL
│       ├── canonical.py    chuẩn hoá nhãn model / iOS
│       ├── filters.py      bộ lọc chung và sinh mệnh đề WHERE
│       ├── latency.py      sổ ghi độ trễ theo route
│       └── routers/        volume, issues, emerging, sentiment, features,
│                           complaints, compare, support, meta, pipeline
└── web/            React 19 + TypeScript + Vite
    └── src/
        ├── lib/            api.ts, filters.tsx (URL state), persona.tsx, palette.ts
        ├── components/     Shell, FilterBar, Chart (ECharts), ui
        └── pages/          Overview, Issues, Emerging, Sentiment, Features,
                            Complaints, Compare, Support, Pipeline
```

Backend chỉ đọc các bảng `gold_*`; tên bảng lấy từ danh sách cố định, tham số đi qua bind parameter của SQLAlchemy, không ghép chuỗi SQL từ đầu vào người dùng. Mỗi phản hồi có dạng `{data, meta}` với `meta` ghi bộ lọc đã áp dụng, số dòng, thời gian truy vấn CSDL và số lần trúng cache. Frontend không có thông tin đăng nhập CSDL; trong Docker, nginx proxy `/api` sang container API.

## Chuẩn hoá nhãn ở tầng ứng dụng

Khi kết nối vào RDS, nhóm phát hiện bộ trích xuất regex ở Silver giữ nguyên chuỗi khớp nên cùng một model có nhiều cách viết: `iPhone 13Pro`, `iPhone13 Pro`, `İphone 13` (chữ İ Thổ Nhĩ Kỳ), `iPhone 16 Promax`. Có 98 nhãn model và 64 nhãn iOS thô, trong đó một số không tồn tại (`iPhone 3 Pro`, `iPhone 9`, `iOS 24.5`). Sửa ở Silver đòi hỏi chạy lại toàn bộ pipeline trên Colab, nên ứng dụng xử lý tạm ở `canonical.py`:

- gấp mọi biến thể về một nhãn chuẩn (chuẩn hoá Unicode NFKD, bỏ khoảng trắng, hạ chữ thường, rồi parse lại): 98 → 41 model, 64 → 58 iOS;
- đưa model/iOS không có thật về `Other / Unspecified` và `iOS Unspecified`;
- khi người dùng lọc theo nhãn chuẩn, API mở rộng ngược thành danh sách nhãn thô trong `WHERE iphone_model IN (...)`.

Khi Silver được sửa và chạy lại, lớp này trở thành ánh xạ đồng nhất, không cần gỡ.

Tương tự, mart `high_impact_complaints` không loại bài "Non-Defect / General Inquiry" nên 374 trong 500 bài đầu là thảo luận chung (ví dụ "why only iMessage is common in the US"). Trang Complaints mặc định ẩn nhóm này và cho bật lại bằng một công tắc.

## Thiết kế giao diện

Giao diện theo hướng bảng điều khiển vận hành: nền xám lạnh hoặc đen than, các panel viền mảnh, một màu nhấn xanh, một màu tín hiệu xanh lá cho trạng thái dữ liệu. Chữ: Bricolage Grotesque cho tiêu đề và số lớn, Manrope cho giao diện, IBM Plex Mono (tabular) cho mọi con số và nhãn kỹ thuật. Có chế độ sáng và tối.

Một số quyết định cụ thể:

- **Mỗi trang mở đầu bằng một câu kết luận** sinh từ dữ liệu, ví dụ trang Issues: "Search & Settings Bug leads with 881 reports, 26,1% of all defect reports and 50% of them negative. The fastest mover last week was Structural Bending, up 300%." Người xem đọc kết luận trước, biểu đồ chỉ để kiểm chứng.
- **Màu phân loại gắn với nhóm tính năng** theo thứ tự cố định (6 nhóm + thảo luận chung), đã kiểm tra bằng bộ kiểm định mù màu cho cả hai chế độ; cảm xúc dùng bộ ba xanh lá / xám / đỏ cố định; mức cảnh báo (watch, elevated, critical) dùng màu trạng thái riêng kèm biểu tượng và chữ, không chỉ dựa vào màu.
- **Bộ lọc toàn cục nằm trong URL** (`?date_from&date_to&model&ios&feature&issue`) nên mỗi góc nhìn chia sẻ được bằng đường dẫn; trang nào không hỗ trợ một chiều lọc thì làm mờ chiều đó kèm tooltip thay vì bỏ qua âm thầm.
- **Mỗi section có một dòng bằng chứng**: mã BR, bảng Gold, endpoint, số dòng, thời gian phản hồi. Khi trình bày, giảng viên nhìn được biểu đồ nào lấy từ đâu.
- **Bộ chọn vai trò** đổi trang mở đầu, thứ tự menu và từ vựng chỉ số (PM thấy "Defect reports", Brand Manager thấy "Conversations").
- Phím `/` mở hộp nhảy nhanh tới trang, model hoặc lỗi.

## Trang và chức năng

| Trang      | BR          | Thành phần chính                                                                                                                                                                                                                    |
| ---------- | ----------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Overview   | BR01        | 5 KPI có delta so kỳ trước; cột ngày + đường trung bình 7 ngày, kéo chọn để đặt khoảng ngày cho toàn ứng dụng; bảng tuần với tăng trưởng; bảng ngày cao điểm kèm bài tiêu cực nổi bật của ngày |
| Issues     | BR02, BR07  | bảng xếp hạng 11 lỗi (số bài, tỷ trọng, thanh cảm xúc, sparkline 14 tuần, delta tuần cuối); bấm một dòng để khoan sâu theo model và iOS; lưới small multiples theo tuần với hệ số góc                       |
| Emerging   | BR03        | heatmap lỗi × ngày theo z-score; feed cảnh báo mới nhất trước; ba thanh trượt ngưỡng; bộ kiểm tra chuỗi hiển thị khối lượng ngày, trung bình 3 ngày và mức nền 14 ngày                                     |
| Sentiment  | BR04        | vùng xếp chồng tỷ lệ ba lớp theo ngày/tuần; net sentiment; bảng theo lỗi và theo model                                                                                                                                      |
| Features   | BR05        | thanh theo nhóm tính năng; biểu đồ phân tán khối lượng – độ tiêu cực, kích thước bong bóng là tương tác; ma trận tính năng × lỗi tô theo tỷ lệ tiêu cực                                              |
| Complaints | BR06        | danh sách phân trang, sắp xếp theo 6 tiêu chí, tìm trong tiêu đề, liên kết về Reddit; tổng tương tác theo lỗi                                                                                                        |
| Compare    | BR08        | chọn 2–4 model hoặc bản iOS lớn; thẻ tổng hợp; cột nhóm theo tính năng cho tỷ trọng và tỷ lệ tiêu cực; biểu đồ toàn cảnh mọi model                                                                            |
| Support    | BR09, BR10  | ma trận lỗi × tháng với cờ tái diễn và độ biến động; nhu cầu hỗ trợ theo nhóm, theo tháng, theo model                                                                                                               |
| Pipeline   | Đánh giá | lineage, 12 kiểm tra đối chiếu chạy trực tiếp trên PostgreSQL, ghi chú chất lượng dữ liệu, độ trễ API theo route, ma trận phủ BR, công nghệ và lựa chọn thay thế                                              |

## Triển khai

```bash
# cần .env có DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD, DB_SSLMODE
docker compose up --build      # web: http://localhost:8080, api: http://localhost:8000/api/docs
```

Chạy phát triển: `uvicorn app.main:app --port 8000` trong `application/api` và `npm run dev` trong `application/web` (Vite proxy `/api` sang cổng 8000).

# Đánh giá

## Độ chính xác của dữ liệu

**Kiểm tra trong pipeline.** Silver dùng `validate_medallion_quality_gates`: `post_id` duy nhất, không thiếu `feedback_year/month`, `is_question` là boolean, `support_category` chỉ có khi `is_question`, không thiếu `sentiment`. Tổng `question_count` của `support_demand` bằng số bài `is_question` trong Silver.

**Kiểm tra ở tầng phục vụ.** Trang Pipeline của ứng dụng chạy 12 truy vấn đối chiếu mỗi lần mở.

| Kiểm tra                                                        | Kỳ vọng   | Thực tế | Kết quả |
| ---------------------------------------------------------------- | ----------- | --------- | --------- |
| `feedback_volume.total_posts` = `issue_summary.total_posts`  | 13 812      | 13 812    | đạt     |
| `sentiment_summary.post_count` = `issue_summary.total_posts` | 13 812      | 13 812    | đạt     |
| `feature_feedback.mention_count` = …                          | 13 812      | 13 812    | đạt     |
| `model_comparison.total_feedback` = …                         | 13 812      | 13 812    | đạt     |
| `issue_trends.weekly_volume` = …                              | 13 812      | 13 812    | đạt     |
| pos + neu + neg trong `issue_summary` = `total_posts`        | 13 812      | 13 812    | đạt     |
| `fact_feedback_summary` (galaxy) = `gold_issue_summary`      | 13 812      | 13 812    | đạt     |
| grain của `issue_summary` không trùng                       | 0           | 0         | đạt     |
| `high_impact_complaints` chỉ chứa bài tiêu cực            | 0           | 0         | đạt     |
| `is_anomaly` khớp quy tắc tài liệu                         | 0 sai lệch | 0         | đạt     |
| không thiếu ngày trong `feedback_volume`                    | 92          | 92        | đạt     |

Cùng một tập 13 812 bài được đếm giống nhau qua bảy mart và bảng sự kiện galaxy, nghĩa là các phép gộp của Gold và bộ nạp Serving không làm mất hay nhân đôi bản ghi.

**Kiểm tra thủ công.** Nhóm mở ngẫu nhiên các bài trong `high_impact_complaints` từ liên kết trên trang Complaints để xem nhãn lỗi và cảm xúc có hợp lý không. Phần lớn đúng; sai sót điển hình là từ khoá "storage" kéo bài hỏi về dung lượng iCloud vào "Search & Settings Bug", và "camera control" kéo bài bàn về nút Camera Control (không phải lỗi) vào "Focus & Exposure Bug". Đây là giới hạn của phân loại theo từ khoá, được ghi lại ở mục 6.4.

**Vấn đề đã phát hiện và cách xử lý.** Nhãn model/iOS chưa chuẩn hoá và BR06 lẫn thảo luận chung (mục 5.2). Ứng dụng xử lý ở tầng API; việc sửa gốc ở `regex_extractor.py` và chạy lại Silver → Gold → Serving nằm trong kế hoạch.

## Hiệu năng

**Pipeline.** Số liệu từ `tests/pipeline_benchmark.py` chạy trên Colab (mẫu 500 bài cho Silver, 40 lần lặp cho truy vấn), được nhóm ghi lại trong `config/pipeline_config.py`:

| Giai đoạn | Lựa chọn chính                                    | Kết quả                                                                                                  |
| ----------- | ---------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| Gold batch  | Spark SQL                                            | nhanh hơn Hadoop MapReduce trên RDD 2,52 lần; dùng chung session với Silver                           |
| Stream BR03 | cửa sổ trượt có trạng thái (`apache_flink`) | 95 935 sự kiện/giây, độ trễ 0,0089 ms/sự kiện, bộ nhớ trạng thái 134,78 KB                     |
| Serving     | PostgreSQL                                           | độ trễ truy vấn trung bình 8,05 ms, RAM đỉnh 39,12 KB, dung lượng 88 KB (bộ dữ liệu benchmark) |
| Lược đồ | galaxy                                               | P99 5,48 ms; hỗ trợ drill-across ba bảng sự kiện trên chiều dùng chung                             |

RoBERTa chậm hơn từ điển nhiều lần (mỗi bài phải qua Transformer) nhưng phân biệt được "battery has been terrible" với "battery is terrific" mà từ điển không làm được; nhóm chấp nhận chi phí này vì Silver chạy theo lô trên GPU.

**Ingestion.** Tháng 7/2026: duyệt khoảng 45,7 triệu bản ghi nén để lọc 4 205 bài; JSONL 18,0 MB → Parquet 3,37 MB (giảm 81%).

**Ứng dụng.** API tự đo mỗi request. Với RDS ở Singapore và máy khách ở Việt Nam, khi cache nguội các endpoint đọc bảng lớn mất 200–700 ms (phần lớn là thời gian PostgreSQL + mạng), khi cache ấm 10–50 ms. Trên lượt thử 137 request qua mọi endpoint với ba bộ lọc khác nhau: P50 224 ms, P95 872 ms, P99 3 038 ms (giá trị P99 đến từ `/pipeline/evidence`, endpoint chạy 15 truy vấn đối chiếu). Frontend tải lần đầu khoảng 400 KB JavaScript nén gzip cộng 380 KB cho ECharts, tách chunk riêng.

## Mức độ đáp ứng yêu cầu nghiệp vụ

| BR   | Bảng Gold                 | Endpoint                                | Trang      | Kết quả nổi bật trên dữ liệu 5–7/2026                                                             |
| ---- | -------------------------- | --------------------------------------- | ---------- | --------------------------------------------------------------------------------------------------------- |
| BR01 | `feedback_volume`        | `/volume/*`                           | Overview   | 13 812 bài, 119 180 bình luận, 150 bài/ngày; đỉnh 6/6 với 2 704 đơn vị thảo luận             |
| BR02 | `issue_summary`          | `/issues/ranking`, `/issues/detail` | Issues     | Search & Settings Bug 881 bài (26,1% lỗi), Charging Failure 550, UI Lag & System Freeze 464             |
| BR03 | `emerging_issues`        | `/emerging/*`                         | Emerging   | 112 cảnh báo, 45 ở mức critical; Charging Failure có nhiều cảnh báo nhất (20)                    |
| BR04 | `sentiment_summary`      | `/sentiment/*`                        | Sentiment  | net sentiment −34,8%; 44,4% bài tiêu cực; UI Lag & System Freeze tiêu cực nhất (−70%)             |
| BR05 | `feature_feedback`       | `/features/matrix`                    | Features   | OS & System Software 1 345 lượt (39,9% lỗi); Touch & Keyboard Lag tiêu cực nhất (83%)               |
| BR06 | `high_impact_complaints` | `/complaints`                         | Complaints | 126 khiếu nại lỗi thật trong top 500; tổng tương tác 38 224                                       |
| BR07 | `issue_trends`           | `/issues/trends`                      | Issues     | Search & Settings Bug giảm 1,12 bài/tuần; Wireless & Cellular Drop −65,8% tuần cuối                 |
| BR08 | `model_comparison`       | `/compare/*`                          | Compare    | iPhone 17 được nhắc nhiều nhất (711); iPhone 17 Pro ít tiêu cực nhất trong dòng 17             |
| BR09 | `recurring_issues`       | `/recurring`                          | Support    | 11/11 lỗi có mặt cả ba tháng; Touch & Keyboard Lag biến động nhất (±28%)                        |
| BR10 | `support_demand`         | `/support/demand`                     | Support    | 9 034 câu hỏi; Other Support 34%, Camera & Photos 17%; Data Transfer & Migration tăng 16% tháng cuối |

Mỗi BR có thể trình diễn độc lập trên dữ liệu thật với bộ lọc ngày, model, iOS, tính năng. Kịch bản demo xuyên suốt: tuần 4/5/2026 Charging Failure tăng 147% tuần-trên-tuần (Issues) → Emerging ghi nhận cảnh báo (Emerging) → bài "3-in-1 charger… peltier cooler" đứng thứ hai về tác động (Complaints) → Battery & Thermal chiếm 40% lỗi trên cả ba model dòng 17 (Compare) → câu hỏi Battery & Charging Support tăng 80% trên iPhone 17 trong tháng 7 (Support).

## Hạn chế

- Phân loại lỗi theo từ khoá nhạy với từ đa nghĩa; chưa có tập nhãn tay để đo precision/recall.
- Chỉ 33% bài nêu model và 8% nêu bản iOS, nên BR08 chỉ so sánh được các model phổ biến; nhiều cảnh báo BR03 rơi vào "Other / Unspecified".
- Ba tháng dữ liệu, một subreddit. BR09 "tái diễn" mới có ý nghĩa thống kê yếu; cần thêm tháng.
- Streaming chưa chạy liên tục; Flink và Kafka Streams được mô phỏng bằng thuật toán cùng ngữ nghĩa.
- Nội dung bình luận chưa được xử lý; sentiment chỉ dựa trên bài đăng.

# Kết luận

Nhóm đã dựng được một đường ống hoàn chỉnh từ kho lưu trữ Reddit nén đến mười bảng tổng hợp trên PostgreSQL và một ứng dụng web khai thác được cả mười yêu cầu nghiệp vụ trên dữ liệu thật của r/iphone trong ba tháng. Kiến trúc Medallion với Parquet trên S3 cho phép chạy lại từng tầng độc lập, điều đã cứu nhóm nhiều lần khi đổi taxonomy. Cấu hình pluggable giúp so sánh công nghệ trong cùng một khung đo thay vì viết năm pipeline khác nhau. Phần đánh giá cho thấy số liệu nhất quán xuyên suốt các tầng, còn hiệu năng của tầng phục vụ đủ cho một dashboard tương tác.

Việc tiếp theo nếu có thời gian: chuẩn hoá nhãn ngay ở Silver và chạy lại, thêm bình luận vào Silver để sentiment đi sâu hơn, gán nhãn tay vài trăm bài để đo chất lượng phân loại, và cho producer PRAW chạy thật để tầng Gold cập nhật hằng ngày.

\newpage

# Phụ lục

## A. Cấu trúc mã nguồn

```
reddit-iphone-feedback-pipeline/
├── config/             pipeline_config.py (cấu hình, taxonomy), gold_marts.py
├── ingestion/
│   ├── historical/     download/, extract/, profiling/, run_historical_ingestion.py
│   └── streaming/      reddit/kafka_praw_producer.py, replay_producer.py
├── nlp/                entity_extraction/, feature_detection/, issue_classification/, sentiment/
├── processing/
│   ├── batch/          bronze_to_silver/, enrichment/, silver_to_gold/ (+ alternatives/)
│   └── streaming/      spark_structured_streaming.py, alternatives/
├── serving/database/   postgres_loader.py, schema_ddl.sql, alternatives/
├── application/        api/ (FastAPI), web/ (React)
├── scripts/            run_pipeline.py
├── tests/              pipeline_benchmark.py, test_*.py
├── notebooks/          DE_ingestion.ipynb, DE_processing.ipynb, historical_posts.ipynb
└── docs/               architecture/, data/, evaluation/, INTEGRATION_GUIDE_VI.md
```

## B. Lệnh chạy pipeline

```bash
# Bronze: một tháng
python -m ingestion.historical.run_historical_ingestion --year 2026 --month 07 --upload-s3

# Silver → Gold → Serving
python -m scripts.run_pipeline --stage silver  --silver-engine pyspark_roberta
python -m scripts.run_pipeline --stage gold    --batch-gold-engine spark_sql --stream-engine apache_flink
python -m scripts.run_pipeline --stage serving --serving-backend postgres --schema-paradigm galaxy

# Kiểm thử
pytest tests/                       # pipeline
cd application/api && pytest        # 32 test, 28 test chạy trên RDS
```

## C. Danh sách endpoint của API

```
GET /api/v1/meta/filters          GET /api/v1/meta/freshness        GET /api/v1/meta/variants
GET /api/v1/volume/daily          GET /api/v1/volume/weekly         GET /api/v1/volume/summary       GET /api/v1/volume/peaks
GET /api/v1/issues/ranking        GET /api/v1/issues/detail         GET /api/v1/issues/trends
GET /api/v1/emerging/alerts       GET /api/v1/emerging/series       GET /api/v1/emerging/heatmap
GET /api/v1/sentiment/timeline    GET /api/v1/sentiment/by-issue    GET /api/v1/sentiment/by-model
GET /api/v1/features/matrix
GET /api/v1/complaints
GET /api/v1/compare/options       GET /api/v1/compare/models        GET /api/v1/compare/ios          GET /api/v1/compare/generations
GET /api/v1/recurring             GET /api/v1/support/demand
GET /api/v1/pipeline/evidence     GET /api/v1/pipeline/latency
```

Tham số lọc chung: `date_from`, `date_to`, `model`, `ios`, `feature`, `issue`, `include_non_defect`. Tài liệu OpenAPI sinh tự động tại `/api/docs`.

## D. Phân công

| Thành viên     | Phần việc                                |
| ---------------- | ------------------------------------------ |
| <Thành viên 1> | Ingestion lịch sử, Bronze, profiling, S3 |
| <Thành viên 2> | Silver, NLP, Gold                          |
| <Thành viên 3> | Serving, benchmark công nghệ, streaming  |
| <Thành viên 4> | Ứng dụng, kiểm tra đối chiếu        |
