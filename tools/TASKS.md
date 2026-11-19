# Hướng dẫn chia việc 2 Đợt — Nhóm VINT023 (5 người + Agent)

> Tài liệu này thiết kế theo mô hình **2 Đợt**:
> - **Đợt 1 (SONG SONG, không ai chờ ai):** cả 5 người làm ngay cùng lúc trên máy riêng, mỗi người ghi ra file **riêng** trong `work_reviews/r23007/` nên **không bao giờ xung đột Git**.
> - **Đợt 2 (Tùng gộp + chốt 1 lần):** gộp 5 file review, chạy bàn giao `v2`, đo `F1`, rồi Phát điền số liệu thật vào `REPORT.md`, Nhân rà checklist và nộp LMS.

---

## Luật đỏ BẮT BUỘC cho cả Người & AI Agent

1. **CẤM TUYỆT ĐỐI** đọc thư mục `runs/*/_private/` (`truth.json`, `trace_truth.json`), cấm chạy `inject_release.py --dev-truth`, cấm chạy `score_findings.py --truth-dir`, cấm dùng `score_findings.py` để dò từng ảnh.
2. **CẤM sửa** bất kỳ file nào trong `scripts/` hoặc trong `runs/*/delivery/`.
3. **CẤM dùng AI nhìn ảnh hộ hoặc bịa nội dung:**
   - Agent **KHÔNG ĐƯỢC** tự xem ảnh để điền `review_log` / `tv*_*.csv`, **KHÔNG ĐƯỢC** tự kết luận `wrong_hash` là nguyên vẹn, **KHÔNG ĐƯỢC** tự bịa tên ảnh mặt người trong `security.md`.
   - Agent chỉ được setup môi trường, chạy validator, mở Web UI `tools/review_app.py` (hoặc tạo file khung), rồi **DỪNG** chờ người thật mở ảnh xem bằng mắt và tự nhập kết luận ≥ 20 ký tự mô tả **thấy gì trong ảnh**.
4. **Mỗi thành viên phải có ≥ 2 commit có nội dung** mang đúng tên + email GitHub của mình. Luôn chạy `git pull --rebase origin main` trước khi `git push`.
5. Nếu bạn dùng AI Agent hỗ trợ ở máy mình, nhớ thêm **1 dòng trung thực** vào [submission/prompts.md](../submission/prompts.md).

---

## Tổng quan 2 Đợt (Seed luyện tập `23007`)

| Đợt | Ai làm | Làm gì | Sản phẩm đầu ra |
|---|---|---|---|
| **Đợt 1** | **Tùng (TV 1)** | Setup chuẩn xong; xem ảnh `000000001818`, `000000014007` | `work_reviews/r23007/tv1_tung.csv` |
| **Đợt 1** | **Phát (TV 2)** | Điền GitHub; test `r23017`; xem `000000005586` (2 ứng viên), `000000014226`; mở kiểm 2 ảnh `wrong_hash` | `submission/TEAM.md`, `work_reviews/r23007/tv2_phat.csv`, `work_reviews/r23007/wrong_hash_check.txt` |
| **Đợt 1** | **Vinh (TV 3)** | *(Đã xong Commit 1 `b536cc7`)*; xem `000000007991`; đối chiếu `trace.json` với `jobs.csv`/`ticket.md`/`changelog.md` | `work_reviews/r23007/tv3_vinh.csv`, `work_reviews/r23007/trace_check_vinh.md` |
| **Đợt 1** | **Thọ (TV 4)** | Điền GitHub; xem `000000009448`; mở Tab 2 tìm 1 ảnh rõ mặt người cho `security.md` | `submission/TEAM.md`, `work_reviews/r23007/tv4_tho.csv`, `submission/r23007/security.md` |
| **Đợt 1** | **Nhân (TV 5)** | Cấp quyền Collaborator cho nhóm; xem `000000012667` | `work_reviews/r23007/tv5_nhan.csv` |
| **Đợt 2** | **Tùng → Phát → Nhân** | Tùng gộp 5 CSV + chạy `build_handover.py` + `export_submission.py` → Phát điền số thật vào `REPORT.md` → Nhân kiểm checklist & nộp LMS | `submission/r23007/*`, `submission/REPORT.md`, `submission/lineage.jsonl` |

*(Ghi chú Windows PowerShell: thay `python3` bằng `py -X utf8`, không nối lệnh bằng `&&` mà chạy từng dòng.)*

---

## Khối 1 — Nguyễn Khánh Tùng (`2A202603144`, GitHub `sfpcshch`) — Bậc 1 (Nặng nhất)

### Tóm tắt cho người làm
1. Đã hoàn thành toàn bộ setup, `validator/validate.py`, `tools/`, hiệu chỉnh `runs/clean` và push sẵn lên `main`.
2. Mở `tools/review_app.py` chọn **TV 1**, xem kỹ bằng mắt 2 ảnh `000000001818` (`missing_box` zebra) và `000000014007` (`cat` vs `pizza`), xuất ra `work_reviews/r23007/tv1_tung.csv` và push.
3. Khi đủ 5 file CSV của cả nhóm + xác nhận `wrong_hash` của Phát + `submission/r23007/security.md` của Thọ -> chạy Đợt 2 (`merge_member_reviews.py` -> `build_handover.py` -> `score_findings.py` -> `export_submission.py` -> push).

### Prompt copy-paste cho Agent của Tùng
```text
Làm theo đúng tools/TASKS.md mục Khối 1 (TV 1 - Nguyễn Khánh Tùng) tại repo K5-L23-DAY10-NHOMVINT023-Release.
TUÂN THỦ LUẬT ĐỎ: KHÔNG đọc runs/*/_private/, KHÔNG sửa scripts/ hay delivery/, KHÔNG tự nhìn ảnh hoặc tự viết ghi chú review hộ tôi.

Đợt 1:
1. Chạy `git pull --rebase origin main`.
2. Khởi chạy `python3 tools/review_app.py --delivery runs/r23007/delivery --candidates runs/r23007/candidates.json --out runs/r23007/review_tv1.csv --rules runs/r23007/rules.json --members 5` (chạy nền hoặc mở trình duyệt) rồi DỪNG chờ tôi tự chọn TV 1 và xem 2 ảnh (000000001818, 000000014007).
3. Khi tôi báo đã review xong: sao chép/kiểm tra `runs/r23007/review_tv1.csv` sang `work_reviews/r23007/tv1_tung.csv` bằng `python3 tools/merge_member_reviews.py` để đảm bảo chuẩn H3, rồi commit và push `work_reviews/r23007/tv1_tung.csv`.

Đợt 2 (chỉ chạy khi tôi báo cả 5 bạn đã push xong file ở Đợt 1):
1. `git pull --rebase origin main`.
2. Gộp đủ 5 file `work_reviews/r23007/tv*.csv` thành `runs/r23007/review_log.csv` bằng `python3 tools/merge_member_reviews.py`.
3. Chép `submission/r23007/security.md` sang `runs/r23007/security.md` (xác nhận không còn `[DIEN_TEN_ANH_CO_MAT_NGUOI_RO]`).
4. Đọc `work_reviews/r23007/wrong_hash_check.txt` của Phát để lấy tên người kiểm (và `--corrupt-hash` nếu có ảnh hỏng thật), chạy:
   `python3 tools/build_handover.py --run runs/r23007 --rules runs/r23007/rules.json --hash-checked-by "<Tên từ file của Phát>"`
5. Chạy `python3 scripts/score_findings.py --run runs/r23007` và `python3 scripts/export_submission.py --run runs/r23007`.
6. Báo lại cho tôi bảng số liệu thật (F1 các loại, QC v1, số ảnh/nhãn v2) để Phát điền nốt `submission/REPORT.md`, rồi commit & push phần `submission/r23007/` và `submission/lineage.jsonl`.
```

---

## Khối 2 — Võ Tiến Phát (`2A202603130`) — Bậc 2 (Nhiều thứ 2)

### Tóm tắt cho người làm
1. **Commit 1 (Đợt 1):** điền GitHub username của Phát vào `submission/TEAM.md`.
2. **Commit 2 (Đợt 1):** tải dữ liệu (dùng `tools/fast_cache_coco.py` trước nếu mạng chậm), kiểm chứng chạy `validator/validate.py` trên seed `23017`; mở `review_app.py` chọn **TV 2** để tự xem 2 ảnh (`000000005586` có 2 ứng viên: `bbox_drift` tennis racket & `missing_box` person; và `000000014226` `instance_merge` chair) -> lưu `work_reviews/r23007/tv2_phat.csv`; đồng thời mở **Tab 2** nhìn bằng mắt 2 ảnh `wrong_hash` (`000000007977`, `000000021839`) và ghi kết luận vào `work_reviews/r23007/wrong_hash_check.txt`.
3. **Commit 3 (Đợt 2):** sau khi Tùng tạo xong gói v2, kiểm tra `rework_queue.csv`/`manifest.csv`/`README.txt` và điền số liệu thật còn thiếu vào Mục 1–2 của [submission/REPORT.md](../submission/REPORT.md).

### Prompt copy-paste cho Agent của Phát
```text
Đọc kỹ tools/TASKS.md mục Khối 2 (TV 2 - Võ Tiến Phát) tại repo K5-L23-DAY10-NHOMVINT023-Release.
LUẬT ĐỎ BẮT BUỘC:
- KHÔNG đọc runs/*/_private/, KHÔNG chạy --dev-truth hay --truth-dir, KHÔNG sửa scripts/ hay delivery/.
- KHÔNG dùng AI nhìn ảnh hộ hay tự viết kết luận cho review_log hoặc wrong_hash. Chỉ mở công cụ để TÔI tự xem bằng mắt và tự gõ nhận xét >= 20 ký tự.
- Nếu cần hỏi GitHub username của tôi để điền TEAM.md, hãy hỏi tôi trước.

Hãy thực hiện Đợt 1 từng bước:
1. Kiểm tra `git config user.name` và `git config user.email`, chạy `git pull --rebase origin main`.
2. Hỏi tôi GitHub username, cập nhật dòng của "Võ Tiến Phát" trong `submission/TEAM.md`, rồi tạo Commit 1 (`P0: cap nhat GitHub Vo Tien Phat trong TEAM.md`) và push.
3. Nếu chưa có `data_source/coco250`, chạy:
   - `python3 tools/fast_cache_coco.py`
   - `python3 scripts/download_public.py`
   - `python3 scripts/run_lab.py --seeds 23007`
   - `python3 scripts/inject_release.py --seed 23017 --out runs/r23017`
4. Chạy validator kiểm chứng trên cả `r23007` và `r23017`:
   - `python3 validator/validate.py runs/r23007/delivery --out runs/r23007/rules.json --candidates runs/r23007/candidates.json`
   - `python3 validator/validate.py runs/r23017/delivery --out runs/r23017/rules.json --candidates runs/r23017/candidates.json`
5. Mở Web UI để TÔI tự xem ảnh:
   `python3 tools/review_app.py --delivery runs/r23007/delivery --candidates runs/r23007/candidates.json --out runs/r23007/review_tv2.csv --rules runs/r23007/rules.json --members 5`
   Nhắc tôi làm ĐỦ 2 VIỆC trong giao diện:
   (a) Chọn "TV 2", nhập tên "Phat", xem kỹ và ghi chú >= 20 ký tự mô tả thấy gì cho:
       - 000000005586 (ảnh này có 2 ứng viên: bbox_drift 'tennis racket' và missing_box 'person' — nhớ xem đủ cả 2!)
       - 000000014226 (instance_merge 'chair')
   (b) Sang Tab 2 ("Wrong Hash & Ảnh Mặt Người"), nhìn bằng mắt 2 ảnh `000000007977` và `000000021839` xem ảnh có mở bình thường và nguyên vẹn không, rồi báo lại kết luận thật cho Agent.
6. DỪNG CHỜ tôi báo đã xem xong. Sau khi tôi xác nhận:
   - Chép `runs/r23007/review_tv2.csv` -> `work_reviews/r23007/tv2_phat.csv` (kiểm tra bằng `python3 tools/merge_member_reviews.py work_reviews/r23007/tv2_phat.csv --out work_reviews/r23007/tv2_phat.csv`).
   - Ghi đúng kết luận tôi vừa kiểm bằng mắt vào `work_reviews/r23007/wrong_hash_check.txt` (ghi rõ tên người kiểm: `Vo Tien Phat`, trạng thái từng ảnh `000000007977` và `000000021839`, nguyên vẹn hay hỏng).
   - Commit 2 (`P2-P4: hoan thanh review TV2 va kiem tra wrong_hash`) gồm 2 file trong `work_reviews/r23007/` và `git pull --rebase origin main && git push origin main`.
```

*(Khi sang Đợt 2 sau khi Tùng push `submission/r23007/`, Phát dùng thêm prompt ngắn này cho Commit 3:)*
```text
Chạy `git pull --rebase origin main`. Đọc `submission/r23007/handover/*/README.txt`, `rework_queue.csv`, `manifest.csv` và kết quả `score_findings.py` từ Tùng. Đối chiếu tính nhất quán (số ảnh, số nhãn, rework có mặt đúng trong errors.json, không sửa nhãn gốc), điền các số liệu thật vào chỗ `[ĐIỀN SAU KHI REVIEW XONG]` ở Mục 1 và Mục 3 của `submission/REPORT.md` (không bịa số), rồi commit & push.
```

---

## Khối 3 — Đinh Thành Vinh (`2A202603044`, GitHub `vdprogramm`) — Bậc 3 (Trung bình)

### Tóm tắt cho người làm
1. *(Bạn đã có sẵn Commit 1 `b536cc7` cập nhật GitHub `vdprogramm` trong `TEAM.md`!)*
2. **Commit 2 (Đợt 1):** mở `review_app.py` chọn **TV 3**, tự nhìn ảnh `000000007991` (xem **Zoom GỐC** để phân biệt vật thật là `spoon` hay `knife` -> chốt `class_swap` hay `category_swap`) -> lưu `work_reviews/r23007/tv3_vinh.csv`; đồng thời chạy `tools/build_trace.py` kiểm tra đối chiếu `trace.json` với `changelog.md`, `ticket.md`, `jobs.csv` (xác nhận không dùng `metadata.json`), ghi biên bản kiểm vào `work_reviews/r23007/trace_check_vinh.md` và push.
3. **Commit 3 (Đợt 2, khuyến khích):** rà lại `submission/lineage.jsonl` (có `HOLD` v1, `R-021`, `release` v2) và Mục 3, 5 của `submission/REPORT.md`.

### Prompt copy-paste cho Agent của Vinh
```text
Đọc kỹ tools/TASKS.md mục Khối 3 (TV 3 - Đinh Thành Vinh, GitHub vdprogramm) tại repo K5-L23-DAY10-NHOMVINT023-Release.
LUẬT ĐỎ BẮT BUỘC:
- KHÔNG đọc runs/*/_private/, KHÔNG chạy --dev-truth hay --truth-dir, KHÔNG sửa scripts/ hay delivery/.
- KHÔNG dùng AI nhìn ảnh hộ hay tự viết ghi chú cho 000000007991. Mở Web UI để TÔI tự nhìn ảnh gốc phân biệt 'spoon' hay 'knife'.

Hãy thực hiện Đợt 1:
1. Kiểm tra `git config user.name` và `git config user.email`, chạy `git pull --rebase origin main`.
2. Nếu máy chưa có dữ liệu, chạy:
   - `python3 tools/fast_cache_coco.py`
   - `python3 scripts/download_public.py`
   - `python3 scripts/run_lab.py --seeds 23007`
   - `python3 validator/validate.py runs/r23007/delivery --out runs/r23007/rules.json --candidates runs/r23007/candidates.json`
3. Chạy `python3 tools/build_trace.py --delivery runs/r23007/delivery --out runs/r23007/trace.json`, sau đó giúp tôi kiểm tra độc lập bằng cách đọc `runs/r23007/delivery/guideline/changelog.md`, `runs/r23007/delivery/incoming/ticket.md`, `runs/r23007/delivery/jobs.csv` và `runs/r23007/delivery/metadata.json` (tìm xem có ảnh nào bị `guideline_mismatch` mà `build_trace.py` đã né được đúng nhờ đọc `jobs.csv` không).
4. Mở Web UI để TÔI tự xem ảnh:
   `python3 tools/review_app.py --delivery runs/r23007/delivery --candidates runs/r23007/candidates.json --out runs/r23007/review_tv3.csv --rules runs/r23007/rules.json --members 5`
   Nhắc tôi chọn "TV 3", nhập tên "Vinh", nhìn khung Zoom GỐC của ảnh `000000007991` để quyết định bên nào đúng (`spoon` hay `knife`) và gõ nhận xét >= 20 ký tự mô tả thấy gì trong ảnh.
5. DỪNG CHỜ tôi xem xong. Khi tôi báo xong:
   - Lưu/kiểm tra `runs/r23007/review_tv3.csv` -> `work_reviews/r23007/tv3_vinh.csv` bằng `merge_member_reviews.py`.
   - Ghi báo cáo kiểm chứng truy vết ngắn gọn vào `work_reviews/r23007/trace_check_vinh.md` (nêu rõ lớp đổi quy tắc `bottle`, scene báo lỗi trong `ticket.md`, job guideline cũ `v1.2`, số ảnh `tier_a`/`tier_b`, danh sách `notify` đúng trong `jobs.csv`, và xác nhận `build_trace.py` đã bỏ qua đúng trường hợp `guideline_mismatch` ở `metadata.json`).
   - Commit (`P2-P5: hoan thanh review TV3 (000000007991) va kiem chung trace.json`) gồm 2 file trong `work_reviews/r23007/`, rồi `git pull --rebase origin main && git push origin main`.
```

---

## Khối 4 — Phạm Đức Thọ (`2A202603182`) — Bậc 4 (Nhẹ - Trung bình)

### Tóm tắt cho người làm
1. **Commit 1 (Đợt 1):** điền GitHub username của Thọ vào `submission/TEAM.md` và push.
2. **Commit 2 (Đợt 1):** mở `review_app.py` chọn **TV 4**, tự nhìn bằng mắt ảnh `000000009448` (`missing_box` / `person`) -> lưu `work_reviews/r23007/tv4_tho.csv`; đồng thời chuyển sang **Tab 2** tự chọn **1 ảnh có mặt người nhìn rõ**, điền vào mục 3 của `submission/r23007/security.md` (dựa theo khung có sẵn ở `runs/r23007/security.md`, kết luận **Hold + báo người phụ trách**) và push.

### Prompt copy-paste cho Agent của Thọ
```text
Đọc kỹ tools/TASKS.md mục Khối 4 (TV 4 - Phạm Đức Thọ) tại repo K5-L23-DAY10-NHOMVINT023-Release.
LUẬT ĐỎ BẮT BUỘC:
- KHÔNG đọc runs/*/_private/, KHÔNG chạy --dev-truth hay --truth-dir, KHÔNG sửa scripts/ hay delivery/.
- KHÔNG dùng AI nhìn ảnh hộ hay tự chọn ảnh mặt người trong security.md hoặc tự viết ghi chú cho 000000009448. Mở Web UI để TÔI tự nhìn bằng mắt.

Hãy thực hiện Đợt 1:
1. Kiểm tra `git config user.name` và `git config user.email`, chạy `git pull --rebase origin main`.
2. Hỏi tôi GitHub username, cập nhật dòng của "Phạm Đức Thọ" trong `submission/TEAM.md`, rồi tạo Commit 1 (`P0: cap nhat GitHub Pham Duc Tho trong TEAM.md`) và push.
3. Nếu máy chưa có dữ liệu, chạy:
   - `python3 tools/fast_cache_coco.py`
   - `python3 scripts/download_public.py`
   - `python3 scripts/run_lab.py --seeds 23007`
   - `python3 validator/validate.py runs/r23007/delivery --out runs/r23007/rules.json --candidates runs/r23007/candidates.json`
4. Mở Web UI để TÔI tự xem ảnh:
   `python3 tools/review_app.py --delivery runs/r23007/delivery --candidates runs/r23007/candidates.json --out runs/r23007/review_tv4.csv --rules runs/r23007/rules.json --members 5`
   Nhắc tôi làm 2 việc:
   (a) Ở Tab 1: chọn "TV 4", nhập tên "Tho", tự nhìn ảnh `000000009448` (`missing_box` lớp `person`), gõ mô tả >= 20 ký tự thấy gì trong ảnh và bấm Confirm/Reject.
   (b) Sang Tab 2 ("Wrong Hash & Ảnh Mặt Người"): tự nhìn các ảnh `person` được gợi ý, chọn **1 tên ảnh** có khuôn mặt người nhìn rõ (không bị che/quay lưng) và báo tên ảnh đó cho Agent.
5. DỪNG CHỜ tôi xem xong. Khi tôi báo xong và đưa mã ảnh mặt người:
   - Chép `runs/r23007/review_tv4.csv` -> `work_reviews/r23007/tv4_tho.csv` (kiểm tra chuẩn H3 bằng `merge_member_reviews.py`).
   - Tạo `submission/r23007/security.md` dựa trên khung nội dung ở `templates/security.md` (hoặc chép từ bản đã soạn gắn với `lab250_35a1b97339da`, nhớ giữ nguyên tiêu đề có dấu `## 3. Ca khuôn mặt`, mỗi mục >= 80 ký tự không khoảng trắng, kết luận Hold + báo người phụ trách, thay đúng tên ảnh tôi vừa chọn vào mục 3 và xóa sạch mọi dấu `<<...>>` hay `[DIEN_...]`).
   - Commit 2 (`P2-P6: hoan thanh review TV4 va security.md ca khuon mat`) gồm `work_reviews/r23007/tv4_tho.csv` và `submission/r23007/security.md`, rồi `git pull --rebase origin main && git push origin main`.
```

---

## Khối 5 — Nguyễn Hoàng Nhân (`2A202603246`, GitHub `Nhan1724`) — Bậc 5 (Nhẹ nhất)

### Tóm tắt cho người làm
1. **Commit 1 (Đợt 1):** kiểm tra đã add đủ 4 bạn (`sfpcshch`, `vdprogramm`, GitHub của Phát & Thọ) làm Collaborator trên repo; mở `review_app.py` chọn **TV 5**, tự nhìn bằng mắt ảnh `000000012667` (`bbox_drift` / `banana`), ghi chú ≥ 20 ký tự mô tả vị trí box so với quả chuối -> lưu `work_reviews/r23007/tv5_nhan.csv` và push.
2. **Commit 2 (Đợt 2):** sau khi Tùng & Phát chốt xong `submission/r23007/` và `REPORT.md`, chạy `git log --format="%an <%ae>"` xác nhận đủ 5 người × ≥ 2 commit, rà checklist `SUBMISSION.md`, cập nhật dòng xác nhận cuối (nếu cần) và nộp link repo lên LMS.

### Prompt copy-paste cho Agent của Nhân
```text
Đọc kỹ tools/TASKS.md mục Khối 5 (TV 5 - Nguyễn Hoàng Nhân, GitHub Nhan1724) tại repo K5-L23-DAY10-NHOMVINT023-Release.
LUẬT ĐỎ BẮT BUỘC:
- KHÔNG đọc runs/*/_private/, KHÔNG chạy --dev-truth hay --truth-dir, KHÔNG sửa scripts/ hay delivery/.
- KHÔNG dùng AI nhìn ảnh hộ hay tự viết ghi chú cho 000000012667. Mở Web UI để TÔI tự xem bằng mắt.

Hãy thực hiện Đợt 1:
1. Kiểm tra `git config user.name` và `git config user.email`, chạy `git pull --rebase origin main`.
2. Nếu máy chưa có dữ liệu, chạy:
   - `python3 tools/fast_cache_coco.py`
   - `python3 scripts/download_public.py`
   - `python3 scripts/run_lab.py --seeds 23007`
   - `python3 validator/validate.py runs/r23007/delivery --out runs/r23007/rules.json --candidates runs/r23007/candidates.json`
3. Mở Web UI để TÔI tự xem ảnh:
   `python3 tools/review_app.py --delivery runs/r23007/delivery --candidates runs/r23007/candidates.json --out runs/r23007/review_tv5.csv --rules runs/r23007/rules.json --members 5`
   Nhắc tôi chọn "TV 5", nhập tên "Nhan", mở ảnh `000000012667` (`bbox_drift` lớp `banana`), tự quan sát box có bị lệch/thiếu phần nào của quả chuối không rồi gõ mô tả >= 20 ký tự.
4. DỪNG CHỜ tôi xem xong. Khi tôi báo xong:
   - Chép `runs/r23007/review_tv5.csv` -> `work_reviews/r23007/tv5_nhan.csv` (kiểm tra bằng `merge_member_reviews.py`).
   - Commit 1 (`P2: hoan thanh review TV5 (000000012667)`) gồm `work_reviews/r23007/tv5_nhan.csv`, rồi `git pull --rebase origin main && git push origin main`.
5. Nhắc tôi kiểm tra trên GitHub Settings -> Collaborators đã cấp quyền Write cho cả 4 bạn còn lại chưa.

(Đợt 2 - cuối buổi sau khi Tùng & Phát hoàn tất `submission/r23007/` và `REPORT.md`: chạy `git pull --rebase origin main`, chạy `git shortlog -sn --all` để kiểm tra đủ 5 thành viên mỗi người >= 2 commit, chạy `python3 scripts/check_handover.py --run runs/r23007` đảm bảo 17/17 PASS, kiểm tra `README.md` đã đổi tiêu đề thành `# Day 10 Lab — Nhóm VINT023`, rồi nộp link repo lên LMS.)
```

---

## Đợt thi Đề Ẩn (40 phút tại lớp) — Vận hành 1 máy chủ LAN hoặc 5 máy

1. **Cách nhanh nhất (cùng phòng WiFi lớp — chỉ 1 người giải nén `de_an.zip`):**
   - Tùng giải nén `de_an.zip` thành `./delivery/` rồi chạy:
     ```bash
     python3 tools/run_de_an.py prepare --launch-ui --lan
     ```
   - Terminal sẽ in ra link LAN dạng `http://192.168.x.x:8765/`. Cả 5 người mở link đó trên trình duyệt máy mình: mỗi người chọn đúng shard **TV 1**..**TV 5**, nhập tên, tự xem ảnh thật và lưu trực tiếp vào `submission/de_an/review_log.csv`.
   - Đủ hết ứng viên -> Tùng bấm `Ctrl+C` tắt server, chạy `python3 tools/run_de_an.py finalize`, kiểm tra đủ 4 file trong `submission/de_an/` rồi `git add submission/de_an && git commit && git push`.
2. *(Nếu WiFi lớp chặn LAN giữa các máy)*: mỗi người giải nén `de_an.zip` trên máy mình (hoặc Tùng gửi file `candidates.json` + `delivery`), chạy `prepare` -> mở `review_app.py` chọn **TV 1..TV 5** -> bấm **Tải CSV phần của mình** gửi về cho Tùng chạy `merge_member_reviews.py` -> `finalize` -> push.
