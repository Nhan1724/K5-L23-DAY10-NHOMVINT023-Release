# Bảo mật khi làm việc — Lô luyện tập r23007 (Nhóm VINT023)

## 1. Ca USB: hết giờ, muốn chép lô về nhà làm tiếp
Không được phép chép lô ảnh `r23007` (250 ảnh và nhãn detection/panoptic) ra USB cá nhân để mang về nhà làm tiếp. Việc tự gửi dữ liệu qua email cá nhân, tải lên kho lưu trữ riêng hoặc nhờ người ngoài làm hộ cũng đều sai nghiêm trọng vì làm dữ liệu dự án thoát khỏi vùng kiểm soát truy cập, dễ gây rò rỉ thông tin nhạy cảm, vi phạm cam kết bảo mật (NDA) và làm mất dấu vết người thao tác. Cách xử lý đúng là dừng công việc khi hết ca, lưu tiến độ trên hệ thống nội bộ được cấp quyền, bàn giao lại cho ca sau hoặc đề xuất quản lý cấp quyền làm việc từ xa chính thức qua VPN/máy công ty được phê duyệt.

## 2. Năm việc: được hay không
- **Mở job được giao trên máy công ty:** **Được**, vì đây là thiết bị thuộc phạm vi quản lý bảo mật của tổ chức và người làm chỉ truy cập đúng job được phân công trong `jobs.csv`.
- **Chụp màn hình gửi người quen:** **Không**, vì ảnh trong lô là dữ liệu thuộc phạm vi dự án, chụp và gửi ra ngoài làm rò rỉ dữ liệu khách hàng/dự án cho người không có thẩm quyền.
- **Chép lô ra USB:** **Không**, vì USB cá nhân không nằm trong kiểm soát của hệ thống, dễ bị thất lạc, nhiễm mã độc hoặc phát tán bản sao trái phép.
- **Dán nhãn thật lên chatbot:** **Không**, vì gửi nội dung nhãn thật hoặc metadata của lô lên dịch vụ AI bên thứ ba có nguy cơ lưu trữ và rò rỉ dữ liệu nội bộ ra ngoài.
- **Đưa tài khoản CVAT cho đồng nghiệp:** **Không**, vì dùng chung tài khoản làm sai lệch toàn bộ lịch sử truy vết (`annotator`/`reviewer` trong `jobs.csv` và `truyvet.csv`), không thể quy trách nhiệm chính xác khi có lỗi bàn giao.

## 3. Ca khuôn mặt: thấy mặt người rõ trong lô, guideline yêu cầu làm mờ
Khi kiểm tra bằng mắt các ảnh có lớp `person` lớn trong lô `r23007`, phát hiện nhiều ảnh thấy rất rõ khuôn mặt người nhìn trực diện chưa được làm mờ, tiêu biểu là ảnh **`000000001296`** (chân dung cận mặt một phụ nữ mặc áo trắng đang cầm điện thoại ốp lưng Hello Kitty, khuôn mặt không hề bị che khuất) và ảnh **`000000004395`** (cận mặt một người đàn ông mặc áo sơ mi trắng thắt cà vạt). Nếu guideline của dự án yêu cầu làm mờ khuôn mặt để bảo vệ dữ liệu cá nhân, trạng thái lô bắt buộc phải đặt là **Hold** (tạm dừng bàn giao/huấn luyện) và **báo ngay cho người phụ trách dự án / quản lý dữ liệu (PM/Tech Lead)** cùng danh sách các mã ảnh vi phạm. Tuyệt đối **không tự ý làm mờ ảnh hay tự xóa ảnh** ngay trong lô vì tự chỉnh sửa ảnh sẽ làm thay đổi mã `sha256` gây sai lệch `manifest.csv` và phá vỡ tính bất biến của bản v1 trong lineage, còn tự ý xóa sẽ làm lệch số lượng mẫu và cấu trúc split đã thống nhất; việc ẩn danh (làm mờ khuôn mặt) phải được thực hiện theo quy trình chuẩn và phát hành thành phiên bản dữ liệu mới có ghi nhận đầy đủ.
