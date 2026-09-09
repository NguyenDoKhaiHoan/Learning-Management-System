# Tiến độ LMS ↔ Google Sheet

Đây là nơi lưu link và trạng thái được xác minh để mỗi lần bạn yêu cầu **“cập nhật
tiến độ LMS lên Google Sheet”**, trợ lý đọc cấu hình, kiểm tra phần vừa làm và đồng bộ.
Không cần sửa từng ô trên Google Sheet. Đây là công cụ chạy theo yêu cầu, chưa có
lịch chạy nền hoặc khả năng tự kết luận task hoàn thành từ code.

## Cấu trúc

- `google-sheet.json`: dán link Google Sheet, tên tab (mặc định `Plan`).
- `tasks.json`: WBS, tiến độ, tên đối chiếu và bằng chứng; nguồn đồng bộ trạng thái.
- `sync.py`: kiểm tra local, preview hoặc ghi F/G lên sheet.
- `AGENTS.md`: quy tắc cho trợ lý khi cập nhật tiến độ.
- `.secrets/google-service-account.json`: khóa truy cập riêng trên máy, bị Git bỏ qua.
- `last-sync.json`: nhật ký lần ghi thành công; không chứa khóa/token.

## Kết nối một lần

1. Upload Master Plan LMS.xlsx vào Drive và mở/chuyển thành **Google Sheets**.
2. Dán URL đầy đủ vào `spreadsheet_url` trong `google-sheet.json`; điền đúng tên tab.
3. Trong Google Cloud, bật **Google Sheets API**, tạo Service Account và tải JSON key.
   Lưu key tại `.secrets/google-service-account.json` trong thư mục này. Không gửi key qua chat.
4. Share **chính Google Sheet đó** cho `client_email` của Service Account với quyền Editor.
   Link chia sẻ đơn thuần không cấp quyền ghi cho công cụ. Nếu tổ chức chặn Service Account,
   cần dùng OAuth người dùng riêng; công cụ hiện tại chưa triển khai cách đó.
5. Cài dependency riêng cho công cụ, từ thư mục gốc repository:

```powershell
uv --system-certs pip install --python .venv/Scripts/python.exe -r lms-platform/progress/requirements.txt
```

CLI dùng `truststore` để xác thực HTTPS bằng kho CA hệ điều hành, bao gồm Windows.
Không cần tắt TLS verification khi mạng máy dùng CA riêng.

## Sử dụng

```powershell
# Kiểm tra trạng thái local, chưa cần Google
.venv/Scripts/python -X utf8 lms-platform/progress/sync.py --local

# Đọc Sheet và xem thay đổi dự kiến; không ghi
.venv/Scripts/python -X utf8 lms-platform/progress/sync.py

# Đồng bộ các thay đổi và đọc lại để kiểm tra
.venv/Scripts/python -X utf8 lms-platform/progress/sync.py --apply
```

Hoặc yêu cầu trợ lý: **“Đối chiếu phần vừa hoàn thành và cập nhật tiến độ LMS theo
thư mục lms-platform/progress lên Google Sheet.”** Trợ lý cập nhật tasks.json và chạy
công cụ thay bạn khi link/quyền đã sẵn sàng. Có thể thêm task của các tuần sau vào JSON.

## Quy tắc dữ liệu

Sheet theo mẫu Master Plan: **A=WBS, B=Công việc, F=Trạng thái, G=Tỉ lệ**.
WBS phải lưu dạng text (`1.10` khác `1.1`). Không dùng số hàng làm ID vì chèn/sắp xếp
hàng có thể làm lệch. Công cụ yêu cầu cả WBS và tên task khớp để tránh cập nhật nhầm.
Đổi tên trên Sheet thì đối chiếu và cập nhật `sheet_titles` của task tương ứng.

Tiến độ số từ 0 đến 1: 0 = Chưa thực hiện; 1 = Đã hoàn thành; giữa hai giá trị =
Đang thực hiện. Có bằng chứng và ngày xác minh cho mỗi mục. Tỷ lệ task đang làm cần
dựa trên checklist đã kiểm tra, không suy từ số file hoặc số dòng code.

15 task tuần 1 đã được đối chiếu và hoàn thành tại checkpoint 09/09/2026, gồm 37 test
backend và 5 test sync đạt; CI có cấu hình và kiểm chứng local, chưa có remote run.
Task schema đã được mô tả lại là SQL thuần;
tên ORM cũ được nhận diện để vẫn khớp sheet cũ. Các tuần 2–8 không bị thay đổi.

Công cụ **chỉ ghi F/G của task theo dõi**, giữ nguyên công thức dòng tổng hợp,
timeline, owner, deadline và định dạng. Màu trạng thái tiếp tục do conditional formatting
của mẫu xử lý. Không tạo tab mới hoặc xóa nội dung sheet.

`tasks.json` là nguồn trạng thái được chọn khi dùng `--apply`: nếu bạn sửa F/G trực tiếp
trên sheet, preview sẽ thể hiện khác biệt trước khi ghi lại theo JSON. Không chỉnh
sheet đồng thời lúc sync; Google Sheets values API không có atomic compare-and-set.
Nếu lỗi mạng sau khi ghi, chạy preview lại trước khi thử tiếp.

## Kiểm thử

```powershell
.venv/Scripts/python -m unittest discover -s lms-platform/progress/tests -v
```

Tham khảo: [Google Sheets values API](https://developers.google.com/workspace/sheets/api/guides/values).
