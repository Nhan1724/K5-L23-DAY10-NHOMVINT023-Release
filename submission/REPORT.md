# Báo cáo nhóm VINT023

## 1. Số liệu luyện tập
- F1 theo seed (rule / cross_check / overall):
  - `r23007` (sau review mắt đầy đủ 8 ứng viên / 7 ảnh, tổng 17 lỗi nộp): `F1 tổng ≈ 0.9 · lỗi luật ≈ 1.0 · lỗi gán nhãn ≈ 0.8`, `trace ≈ tier_a 1.0 · tier_b 1.0 · notify 1.0`
  - `r23017` (kiểm chứng validator): `rule ≈ 1.0` (11 lỗi luật), `trace ≈ tier_a 1.0 · tier_b 1.0 · notify 1.0`
  - `de_an_07` (đề ẩn đã chọn): validator bắt **8 lỗi luật** và khoanh **14 ứng viên / 14 ảnh** (`bbox_drift: 6`, `class_swap_or_category_swap: 5`, `instance_merge: 2`, `missing_box: 1`); 5 thành viên đã review đủ 14/14 dòng (`11 confirmed`, `3 rejected`) tạo **19 lỗi** trong `submission/de_an/errors.json`, và truy vết `submission/de_an/trace.json` xác định `tier_a: 2 ảnh`, `tier_b: 9 ảnh`, `notify: 4 người` (`A03, A04, Q01, Q03`).
- Số ứng viên trên lô sạch (`--no-faults`, `runs/clean`, 50 ảnh pool `calib`): **0 lỗi luật** và **0 ứng viên** sau khi lọc ownership Stage 1 cho `instance_merge`; hàng đợi trên seed luyện tập `r23007`: **8 ứng viên / 7 ảnh** (`bbox_drift: 2`, `class_swap_or_category_swap: 2`, `instance_merge: 1`, `missing_box: 3`); trên `r23017`: **13 ứng viên / 13 ảnh**.
- Ngưỡng đã chọn và cách chọn (không dùng `_private`):
  - Đo trực tiếp phân bố tự nhiên trên 50 ảnh sạch `runs/clean` (`calib`): toàn bộ cặp khớp cùng lớp sạch có `outside_ratio <= 0.003`, `bbox_iou >= 0.908`, `center_dist <= 0.039`, `declared_area - actual_mask_px == 0`, và segment thing chưa ghép lớn nhất chỉ `299 px`.
  - Chọn ngưỡng `bbox_drift` (`outside_ratio >= 0.03`, hoặc `iou < 0.86` kèm lệch tâm/mép và không bị vật khác che `occluder_share < 0.35`), `missing_box` (`seg_area >= 200 px` và `seg_bbox_norm_area >= 0.006`), và bắt buộc `instance_merge` phải có ít nhất một box chưa ghép 1-to-1 ở Stage 1 cùng ăn vào segment. Trước khi thêm điều kiện Stage 1 này, `runs/clean` từng sinh 11 ứng viên giả `instance_merge` ở các ảnh đông người/động vật chồng lấp; sau khi sửa giảm về 0 ứng viên giả.

## 2. Vì sao báo hết ứng viên làm F1 giảm?
Điểm đánh giá là **F1** trên tập cặp `(type, target)`, tức `F1 = 2 * precision * recall / (precision + recall)`. Nếu nhóm nộp thẳng toàn bộ ứng viên (hoặc dùng ngưỡng ghép lỏng gây nhiều ca lệch tự nhiên COCO rồi `confirmed` hết không mở ảnh kiểm):
1. Mọi ứng viên do lệch tự nhiên hoặc trùng ghép sẽ biến thành **FP (false positive)**, làm `precision = TP / (TP + FP)` sụt giảm mạnh so với mức kiểm riêng lỗi luật (`r23007` trước review đạt `rule F1 ≈ 1.0`, `overall F1 ≈ 0.8`). Thực tế trên `r23007`, validator khoanh vùng **8 ứng viên / 7 ảnh**, nhưng sau khi cả nhóm mở Web UI `review_app.py` soi từng ảnh bằng mắt chỉ có **7/8 ứng viên là lỗi thật (`confirmed`)**, còn **1/8 ứng viên (`000000005586` `bbox_drift` trên `tennis racket`) là nhiễu tự nhiên (`rejected`)** do tay người che nhẹ cán vợt (`occluder_share = 0.23`). Nhờ loại bỏ FP này qua mắt người, precision được giữ ở mức cao (nâng `F1 tổng` lên `≈ 0.9`).
2. Ngoài ra với cặp bất đồng lớp (`class_swap` vs `category_swap`), đoán bừa sai phía sẽ vừa chịu **1 FP** (báo sai loại) vừa chịu **1 FN** (bỏ sót loại đúng) — ví dụ trên `r23007`, cả 2 ca bất đồng lớp (`000000007991` và `000000014007`) sau khi mở ảnh thật đều xác định đúng hướng là `category_swap` (nhãn detection đúng, panoptic gán sai). Do đó bắt buộc phải đối chiếu hai nguồn có dùng pixel mask rồi mở từng ảnh xem bằng mắt (nhờ khung zoom gốc không che trong `tools/review_app.py`) để giữ precision cao.

## 3. Quyết định và lineage
- QC v1 (`runs/r23007`, `lab250_35a1b97339da`): **17/250 = 6.8%** (gồm 10 lỗi luật và 7 lỗi gán nhãn ngữ nghĩa đã `confirmed` qua mắt người) — vượt ngưỡng 2% (`5/250`) nên kết luận **HOLD** (không dùng v1 để train, giữ nguyên v1 và tách lô sạch `lab250_35a1b97339da_v2` gồm **241 ảnh / 1671 nhãn** và đưa **9 ảnh** lỗi detection/thiếu file vào `rework_queue.csv`).
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
