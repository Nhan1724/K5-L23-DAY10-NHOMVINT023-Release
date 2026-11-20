Release: lab250_35a1b97339da_v2
Parent: lab250_35a1b97339da
Số ảnh: 241
Số nhãn: 1671
Guideline: v1.2 (J01–J04), v1.3 (J05–J10)
QC v1: 17/250 = 6.8%
Kết luận v1: Hold — tỉ lệ lỗi 17/250 = 6.8% vượt ngưỡng 2% (5/250); không dùng v1 để train, giữ nguyên v1 và tách lô v2 sạch.
Kết luận v2: Release — đã tách 9 ảnh lỗi nhãn detection/thiếu file sang rework_queue.csv; sửa đồng nhất hash, guideline theo job và split theo cảnh; giữ nguyên nhãn gốc cho 241 ảnh.
Ghi chú: wrong_hash (000000007977, 000000021839): Vo Tien Phat đã mở ảnh kiểm, ảnh nguyên vẹn nên giữ ở v2 và ghi sha256 mới tính lại trong manifest.csv; guideline_mismatch (000000013201): sửa trường guideline trong truyvet.csv khớp jobs.csv; scene_leak (scene_337->train): đưa cả cảnh về một split thống nhất trong truyvet.csv; rework (9 ảnh): tách khỏi v2 và giao đúng cặp gán/kiểm (A01/Q02, A01/Q03, A03/Q01, A03/Q02, A04/Q01, A04/Q02, A05/Q02); lỗi chỉ ở panoptic (000000007991 (category_swap), 000000014007 (category_swap), 000000014226 (instance_merge), 000000019786 (thing_overlap)): nhãn detection vẫn đúng nên giữ ở lại v2, đã ghi nhận để báo team panoptic xử lý riêng.
