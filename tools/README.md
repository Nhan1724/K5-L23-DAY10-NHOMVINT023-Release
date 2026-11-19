# Tools hỗ trợ của nhóm VINT023

Các công cụ nằm trong `tools/` (tuân thủ `RULES.md`: không sửa `scripts/`, không đọc `_private/`). `validator/validate.py` là thư viện chuẩn độc lập, **không** import gì từ `tools/`.

## Lệnh nhanh cho Pha 0–5 (Seed luyện tập `23007`)

```bash
# 0. Nếu mạng chậm khi tải ZIP 1.1 GB, chạy cache phần val2017 (~41 MB) trước rồi chạy download_public.py:
python3 tools/fast_cache_coco.py
python3 scripts/download_public.py

# 1. Chạy validator (bắt 9 lỗi luật + sinh ứng viên đối chiếu)
python3 validator/validate.py runs/r23007/delivery \
  --out runs/r23007/rules.json \
  --candidates runs/r23007/candidates.json

# 2. Mở Web UI review ảnh (hỗ trợ chia 5 phần TV 1..TV 5, soi wrong_hash & tìm ảnh mặt người)
python3 tools/review_app.py \
  --delivery runs/r23007/delivery \
  --candidates runs/r23007/candidates.json \
  --out runs/r23007/review_log.csv \
  --rules runs/r23007/rules.json \
  --members 5

# (Nếu 5 người review trên 5 máy riêng, xuất CSV từng người rồi gộp lại:)
python3 tools/merge_member_reviews.py review_tv1.csv review_tv2.csv ... --out runs/r23007/review_log.csv

# 3. Sinh truy vết ticket (Pha 5)
python3 tools/build_trace.py --delivery runs/r23007/delivery --out runs/r23007/trace.json

# 4. Bàn giao v2 + lineage + đóng gói + check_handover (Pha 3-4)
python3 tools/build_handover.py --run runs/r23007 --rules runs/r23007/rules.json

# 5. Tự đo F1 và xuất bài sang submission/
python3 scripts/score_findings.py --run runs/r23007
python3 scripts/export_submission.py --run runs/r23007
```

## Lệnh nhanh cho Đề ẩn (40 phút cuối buổi)

```bash
# Sau khi giải nén de_an.zip thành ./delivery/
python3 tools/run_de_an.py prepare --launch-ui

# (Nếu review trên 5 máy khác nhau, gộp CSV về submission/de_an/review_log.csv:)
python3 tools/merge_member_reviews.py csv1.csv csv2.csv ... --out submission/de_an/review_log.csv

# Sau khi review xong toàn bộ ứng viên
python3 tools/run_de_an.py finalize
```
