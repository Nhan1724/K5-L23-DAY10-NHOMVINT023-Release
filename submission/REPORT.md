# Báo cáo nhóm VINT023

## 1. Số liệu luyện tập
- F1 theo seed (rule / cross_check / overall):
  - `r23007` (trước review mắt): `rule ≈ 1.0` (10 lỗi luật), `trace ≈ tier_a 1.0 · tier_b 1.0 · notify 1.0`; `cross_check` & `overall`: `[ĐIỀN SAU KHI REVIEW XONG]`
  - `r23017` (kiểm chứng validator): `rule ≈ 1.0` (11 lỗi luật), `trace ≈ tier_a 1.0 · tier_b 1.0 · notify 1.0`
- Số ứng viên trên lô sạch (`--no-faults`, `runs/clean`, 50 ảnh pool `calib`): **0 lỗi luật** và **0 ứng viên** sau khi lọc ownership Stage 1 cho `instance_merge`; hàng đợi trên seed luyện tập `r23007`: **7 ứng viên / 7 ảnh** (`bbox_drift: 1`, `class_swap_or_category_swap: 2`, `instance_merge: 1`, `missing_box: 3`); trên `r23017`: **12 ứng viên / 12 ảnh**.
- Ngưỡng đã chọn và cách chọn (không dùng `_private`):
  - Đo trực tiếp phân bố tự nhiên trên 50 ảnh sạch `runs/clean` (`calib`): toàn bộ cặp khớp cùng lớp sạch có `outside_ratio <= 0.003`, `bbox_iou >= 0.908`, `center_dist <= 0.039`, `declared_area - actual_mask_px == 0`, và segment thing chưa ghép lớn nhất chỉ `299 px`.
  - Chọn ngưỡng `bbox_drift` (`outside_ratio >= 0.06`, hoặc `iou < 0.80` kèm lệch tâm/mép và không bị vật khác che `occluder_share < 0.35`), `missing_box` (`seg_area >= 350 px` và `seg_bbox_norm_area >= 0.005`), và bắt buộc `instance_merge` phải có ít nhất một box chưa ghép 1-to-1 ở Stage 1 cùng ăn vào segment. Trước khi thêm điều kiện Stage 1 này, `runs/clean` từng sinh 11 ứng viên giả `instance_merge` ở các ảnh đông người/động vật chồng lấp; sau khi sửa giảm về 0 ứng viên giả.

## 2. Vì sao báo hết ứng viên làm F1 giảm?
Điểm đánh giá là **F1** trên tập cặp `(type, target)`, tức `F1 = 2 * precision * recall / (precision + recall)`. Nếu nhóm nộp thẳng toàn bộ ứng viên (hoặc dùng ngưỡng ghép lỏng gây nhiều ca lệch tự nhiên COCO rồi `confirmed` hết không mở ảnh kiểm):
1. Mọi ứng viên do lệch tự nhiên hoặc trùng ghép sẽ biến thành **FP (false positive)**, làm `precision = TP / (TP + FP)` sụt giảm mạnh (trường hợp ghép thô trên dữ liệu thực tế chỉ đạt F1 ≈ 0,6, thấp hơn cả chỉ kiểm lỗi luật ≈ 0,7).
2. Ngoài ra với cặp bất đồng lớp (`class_swap` vs `category_swap`), đoán bừa sai phía sẽ vừa chịu **1 FP** (báo sai loại) vừa chịu **1 FN** (bỏ sót loại đúng). Do đó bắt buộc phải đối chiếu hai nguồn có dùng pixel mask rồi mở từng ảnh xem bằng mắt (nhờ crop phóng to trong `tools/review_app.py`) để giữ precision cao.

## 3. Quyết định và lineage
- QC v1 (`runs/r23007`, `lab250_35a1b97339da`): `[ĐIỀN SAU KHI REVIEW XONG: <số lỗi>/250 = <x.x%>]` — vượt ngưỡng 2% (`5/250`) nên kết luận **HOLD** (không dùng v1 để train, tách lô sạch v2 không ghi đè v1).
- Vì sao `R-021` phải xem lại hoặc train lại: `runs/lineage.jsonl` ghi nhận training run `R-021` đã dùng dataset `lab250_35a1b97339da` (v1). Việc tạo bản vá v2 (`<release_id>_v2`) **không tự thay đổi trọng số mô hình đã học** từ dữ liệu v1 (vốn chứa ảnh sai lớp, box lệch, thiếu box và rò rỉ split train/val). Vì vậy khi v1 bị `HOLD`, `lineage.py impact` đánh dấu `R-021: affected=True action=review_or_retrain` — bắt buộc phải rà soát đánh giá lại hoặc train lại trên v2 sạch.

## 4. Hash chứng minh gì, không chứng minh gì?
- **Hash (SHA-256) chứng minh được:** tính toàn vẹn ở mức **byte** của file tại thời điểm đóng gói — xác nhận file ảnh/nhãn trong `v2` chưa bị sửa tay, mất byte, hay hỏng trên đường truyền, và bản v1 trong `delivery/` không bị ghi đè (`H1`, `H8`, `H15`).
- **Hash không chứng minh được:** nhãn gán trong file `.txt` có **đúng về mặt ngữ nghĩa hay không**. Một file nhãn bị gán nhầm `car` thành `truck` vẫn có mã SHA-256 hoàn toàn khớp với `manifest.csv`; kiểm chứng đúng sai nhãn vẫn bắt buộc dựa vào đối chiếu đa nguồn và mắt người xem ảnh.

## 5. Truy vết
- **Tiêu chí tách tầng:** lọc theo lớp đổi quy tắc trong `guideline/changelog.md` (`bottle` ở `r23007`) và danh sách scene team AI báo trong `incoming/ticket.md`. Mọi ảnh thuộc job dùng guideline cũ (`v1.2`) có ít nhất một box detection của lớp đó trong `labels/*.txt` được đưa vào:
  - `tier_a`: nằm trong các `scene_id` team AI đã báo.
  - `tier_b`: nằm ở các `scene_id` khác chưa ai báo.
  - `notify`: chỉ tập hợp mã `annotator` và `reviewer` của các job thực sự chứa ảnh `tier_a` hoặc `tier_b` trong `jobs.csv`.
- **Vì sao lấy guideline theo job (`jobs.csv`), không theo `metadata.json` của từng ảnh:** trường `guideline_version` ở mức ảnh trong `metadata.json` có thể bị lỗi `guideline_mismatch` (ghi sai phiên bản so với job giao ban đầu). Theo `GUIDE.md` và `check_handover.py`, tiêu chuẩn công việc áp dụng ở cấp đầu job trong `jobs.csv`, nên truy vết theo `jobs.csv` mới khoanh đúng phạm vi ảnh và người chịu trách nhiệm.

## 6. Bug hoặc điểm chưa rõ trong lab (nếu có)
- Không phát hiện bug trong `scripts/`; lưu ý nhỏ khi triển khai: `check_handover.py` (H9) yêu cầu `label_summary.csv` chỉ liệt kê các lớp có số lượng `> 0` cộng dòng `TOTAL`, và (H17) yêu cầu `security.md` giữ đúng tiêu đề có dấu `## 3. Ca khuôn mặt` với tối thiểu 80 ký tự không khoảng trắng ở mỗi mục.
