# Tools hỗ trợ của nhóm VINT023

Các công cụ nằm trong `tools/` (tuân thủ `RULES.md`: không sửa `scripts/`, không đọc `_private/`). `validator/validate.py` chỉ dùng thư viện chuẩn + `scripts/pngutil.py`, **không** import gì từ `tools/`.

> **Phân công chi tiết 2 Đợt + Prompt cho Agent từng người:** xem [TASKS.md](TASKS.md).

## Lệnh nhanh cho Pha 0–5 (Seed luyện tập `23007`)

```bash
# 0. Tải dữ liệu (nếu mạng chậm khi tải 1.1 GB ZIP, chạy fast_cache_coco.py lấy ~41 MB val2017 trước):
python3 tools/fast_cache_coco.py   # tuỳ chọn khi mạng chậm
python3 scripts/download_public.py

# 1. Chạy validator (bắt 9 lỗi luật + sinh ứng viên đối chiếu)
python3 validator/validate.py runs/r23007/delivery \
  --out runs/r23007/rules.json \
  --candidates runs/r23007/candidates.json

# 2. Mở Web UI review ảnh (chia 5 phần TV 1..TV 5, soi wrong_hash & tìm ảnh mặt người)
#    (Thêm --host 0.0.0.0 nếu muốn 5 máy cùng phòng WiFi mở qua mạng LAN)
python3 tools/review_app.py \
  --delivery runs/r23007/delivery \
  --candidates runs/r23007/candidates.json \
  --out runs/r23007/review_log.csv \
  --rules runs/r23007/rules.json \
  --members 5

# Đợt 1: mỗi thành viên xuất/lưu phần của mình vào work_reviews/r23007/tv*.csv để không xung đột Git.
# Đợt 2: gộp 5 file CSV thành runs/r23007/review_log.csv:
python3 tools/merge_member_reviews.py work_reviews/r23007/tv*.csv --out runs/r23007/review_log.csv

# 3. Sinh truy vết ticket (Pha 5)
python3 tools/build_trace.py --delivery runs/r23007/delivery --out runs/r23007/trace.json

# 4. Bàn giao v2 + lineage + đóng gói + check_handover (Pha 3-4)
#    (Bắt buộc truyền --hash-checked-by "<Tên người đã mở Tab 2 kiểm ảnh wrong_hash>")
python3 tools/build_handover.py --run runs/r23007 --rules runs/r23007/rules.json --hash-checked-by "Vo Tien Phat"

# 5. Tự đo F1 và xuất bài sang submission/
python3 scripts/score_findings.py --run runs/r23007
python3 scripts/export_submission.py --run runs/r23007
```

## Lệnh nhanh cho Đề ẩn (40 phút cuối buổi)

```bash
# Sau khi giải nén de_an.zip thành ./delivery/
# (Thêm --lan để mở Web UI cho cả 5 máy cùng WiFi xem song song)
python3 tools/run_de_an.py prepare --launch-ui --lan

# (Hoặc nếu review trên 5 máy rời nhau, gộp CSV về submission/de_an/review_log.csv:)
python3 tools/merge_member_reviews.py csv1.csv csv2.csv ... --out submission/de_an/review_log.csv

# Sau khi review xong toàn bộ ứng viên
python3 tools/run_de_an.py finalize
```
