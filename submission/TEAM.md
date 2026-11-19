# Nhóm VINT023

- Seed luyện tập: `23007`
- Repo: `https://github.com/Nhan1724/K5-L23-DAY10-NHOMVINT023-Release`
- Hướng dẫn từng bước (2 Đợt + Prompt an toàn cho Agent từng người): [tools/TASKS.md](../tools/TASKS.md)

| Họ và tên | MSHV | Tài khoản GitHub | Phần chính (xếp theo tải công việc) |
|---|---|---|---|
| Nguyễn Khánh Tùng | 2A202603144 | sfpcshch | **Tech Lead:** viết `validator/validate.py`, trọn bộ `tools/`, hiệu chỉnh `runs/clean`, review TV 1 (`000000001818`, `000000014007`), gộp Đợt 2 chạy `build_handover.py` & `run_de_an.py` |
| Võ Tiến Phát | 2A202603130 | [điền GitHub] | **QA Validator & Gói v2:** kiểm chứng `r23017`, review TV 2 (`000000005586` — 2 ứng viên, `000000014226`) + kiểm bằng mắt 2 ảnh `wrong_hash` (`000000007977`, `000000021839`), rà gói v2 & điền số liệu thật Mục 1–2 `REPORT.md` |
| Đinh Thành Vinh | 2A202603044 | vdprogramm | **Lineage & Truy vết:** review TV 3 (`000000007991`: `spoon` vs `knife`), đối chiếu kiểm chứng `trace.json` theo `jobs.csv`/`changelog.md`/`ticket.md`, kiểm `lineage.jsonl` (`R-021`), rà Mục 3 & 5 `REPORT.md` |
| Phạm Đức Thọ | 2A202603182 | [điền GitHub] | **Bảo mật & Hash:** review TV 4 (`000000009448`: `missing_box` / `person`), mở Tab 2 chọn ảnh rõ mặt người & hoàn thiện `security.md` (Hold), rà Mục 4 `REPORT.md` |
| Nguyễn Hoàng Nhân | 2A202603246 | Nhan1724 | **Repo Owner & Submission:** cấp quyền Collaborator, review TV 5 (`000000012667`: `bbox_drift` / `banana`), kiểm checklist `SUBMISSION.md` (≥ 2 commit/người, `check_handover` 0 FAIL) & nộp link LMS |

## Chia ảnh Pha 2 (`r23007` — 8 ứng viên trên 7 ảnh, ghi riêng vào `work_reviews/r23007/tv*.csv`)
- **TV 1 (Tùng):** `000000001818` (`missing_box` / `zebra`), `000000014007` (`class_swap_or_category_swap` / `cat` vs `pizza`) → `tv1_tung.csv`
- **TV 2 (Phát):** `000000005586` (2 ứng viên: `bbox_drift` / `tennis racket` và `missing_box` / `person`), `000000014226` (`instance_merge` / `chair`) → `tv2_phat.csv` + kiểm nguyên vẹn 2 ảnh `wrong_hash` (`000000007977`, `000000021839`) → `wrong_hash_check.txt`
- **TV 3 (Vinh):** `000000007991` (`class_swap_or_category_swap` / `spoon` vs `knife`) → `tv3_vinh.csv` + kiểm truy vết → `trace_check_vinh.md`
- **TV 4 (Thọ):** `000000009448` (`missing_box` / `person`) → `tv4_tho.csv` + ảnh rõ mặt người → `submission/r23007/security.md`
- **TV 5 (Nhân):** `000000012667` (`bbox_drift` / `banana`) → `tv5_nhan.csv`
