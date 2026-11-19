# Báo cáo kiểm chứng truy vết (trace.json) — TV 3 (Đinh Thành Vinh)

## 1. Thông tin đối chiếu từ tài liệu nguồn
- **Lớp đổi quy tắc (`changelog.md`):** `bottle` (`class_id=39`). Phiên bản `v1.3` bắt buộc gán box cho `bottle` bị che trên 50% hoặc bị cắt ở mép ảnh, trong khi bản `v1.2` cho phép bỏ qua.
- **Cảnh báo lỗi trong `ticket.md`:** `scene_829` và `scene_861` (team AI báo cáo tình trạng sót nhiều `bottle` bị che khuất hoặc nằm ở mép ảnh).
- **Job áp dụng guideline cũ `v1.2` (`jobs.csv`):** `J01`, `J02`, `J03`, `J04` (trong đó các job chứa ảnh `bottle` thuộc vùng ảnh hưởng của ticket gồm `J02`, `J03`, `J04`).

## 2. Kết quả đối chiếu `runs/r23007/trace.json`
- **Tầng trực tiếp (`tier_a` — 2 ảnh):** `000000002685`, `000000006471`
- **Tầng mở rộng (`tier_b` — 4 ảnh):** `000000005193`, `000000007574`, `000000008021`, `000000009590`
- **Danh sách nhân sự cần thông báo (`notify`):** `A01`, `A04`, `Q01`, `Q02`, `Q03` (khớp hoàn toàn với danh sách annotator và reviewer của các job `J02`, `J03`, `J04` trong `jobs.csv`).

## 3. Xác nhận độ tin cậy dữ liệu (né lỗi `guideline_mismatch`)
- Trong `delivery/metadata.json` tồn tại ảnh **`000000013201`** bị sai lệch phiên bản guideline (`guideline_mismatch`).
- Công cụ `tools/build_trace.py` đã tra cứu phiên bản guideline và nhân sự trực tiếp từ **`jobs.csv`**, không phụ thuộc vào `metadata.json` nên đã loại bỏ chính xác trường hợp nhiễu này khỏi kết quả truy vết.
