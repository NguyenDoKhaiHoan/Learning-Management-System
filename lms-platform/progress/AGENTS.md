# Cập nhật tiến độ LMS

Khi người dùng yêu cầu cập nhật tiến độ, đọc README.md, google-sheet.json và tasks.json
trong thư mục này. Đối chiếu code và kết quả kiểm thử với tiêu chí của từng task.

- Chỉ đánh dấu hoàn thành khi có bằng chứng; file tồn tại hoặc test pass đơn lẻ không
  chứng minh toàn bộ use case hoàn thành. Schema không đồng nghĩa API/UI đã hoàn thành.
- Cập nhật task theo WBS ổn định, ghi evidence và verified_at. Không đổi WBS để khớp hàng.
- Không giữ trạng thái hoàn thành nếu thay đổi mới làm tiêu chí không còn đúng.
- Khi người dùng yêu cầu đồng bộ Google Sheet, chạy preview rồi --apply nếu preview
  đúng phạm vi; không cần hỏi lại cho chính việc đồng bộ họ đã yêu cầu.
- Nếu thiếu link/quyền truy cập, hoàn thành cập nhật local và báo phần đồng bộ còn thiếu.
- Chỉ đồng bộ task có trong tasks.json. Không ghi đè deadline, owner, tên task, công thức
  tổng hợp, layout hoặc task khác. Hàng phải khớp WBS và tên đã khai báo.
- Không đọc/in private key, token hoặc đưa credentials vào Git.
