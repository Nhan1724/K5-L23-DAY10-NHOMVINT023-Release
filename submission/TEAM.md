# Nhóm VINT023

- Seed luyện tập: `23007`
- Repo: `https://github.com/Nhan1724/K5-L23-DAY10-NHOMVINT023-Release`

| Họ và tên | MSHV | Tài khoản GitHub | Phần chính |
|---|---|---|---|
| Nguyễn Khánh Tùng | 2A202603144 | sfpcshch | Tech Lead: viết `validator/validate.py`, trọn bộ `tools/`, hiệu chỉnh `runs/clean`, review TV 1 (`000000001818`, `000000014007`), chạy `build_handover.py` & điều phối đề ẩn (`run_de_an.py`) |
| Võ Tiến Phát | 2A202603130 | [điền GitHub] | Kiểm thử validator trên seed phụ `r23017`, review TV 2 (`000000005586`, `000000014226`) + kiểm 2 ảnh `wrong_hash` (`000000007977`, `000000021839`), rà gói v2 (`rework_queue.csv`, `manifest.csv`, `README.txt`), điền số liệu Mục 1–2 `REPORT.md` |
| Đinh Thành Vinh | 2A202603044 | [điền GitHub] | Review TV 3 (`000000007991`: phân biệt `spoon` vs `knife`), kiểm chứng Pha 3 (`lineage.jsonl`, `R-021`) & Pha 5 (`trace.json` theo `jobs.csv`), hoàn thiện Mục 3 & 5 `REPORT.md` |
| Phạm Đức Thọ | 2A202603182 | [điền GitHub] | Review TV 4 (`000000009448`: `missing_box` lớp `person`), hoàn thiện Pha 6a `security.md` (chọn ảnh thấy rõ mặt người ở Tab 2 `review_app.py`, kết luận `Hold`), kiểm Mục 4 `REPORT.md` |
| Nguyễn Hoàng Nhân | 2A202603246 | Nhan1724 | Chủ repo (quản lý Collaborator + nộp link LMS), review TV 5 (`000000012667`: `bbox_drift` lớp `banana`), kiểm checklist nộp bài `SUBMISSION.md` & rà đủ ≥ 2 commit/người |

## Chi tiết chia ảnh Pha 2 (`r23007` — 7 ứng viên trên `tools/review_app.py`)
- **TV 1 (Tùng):** `000000001818` (`missing_box` / `zebra`), `000000014007` (`class_swap_or_category_swap` / `cat` vs `pizza`)
- **TV 2 (Phát):** `000000005586` (`missing_box` / `person`), `000000014226` (`instance_merge` / `chair`) + kiểm nguyên vẹn 2 ảnh `wrong_hash` (`000000007977`, `000000021839`)
- **TV 3 (Vinh):** `000000007991` (`class_swap_or_category_swap` / `spoon` vs `knife`)
- **TV 4 (Thọ):** `000000009448` (`missing_box` / `person`) + chọn ảnh có mặt người rõ cho `security.md`
- **TV 5 (Nhân):** `000000012667` (`bbox_drift` / `banana`)
