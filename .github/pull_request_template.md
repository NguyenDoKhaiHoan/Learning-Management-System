## Vấn đề và thay đổi

Mô tả trigger, hành vi trước/sau và phạm vi module.

## Kiểm chứng

- [ ] Test happy path và ít nhất một error path; nêu lệnh/kết quả.
- [ ] Quyền truy cập, scope tài nguyên, validation và state transition đã kiểm tra.
- [ ] SQL dùng bind parameters; transaction và rollback rõ ràng.
- [ ] Có migration thủ công/seed khi cần; không sửa revision đã áp dụng.
- [ ] Error contract/trace_id và audit cho hành động nhạy cảm đã kiểm tra.
- [ ] Shared contracts, README và tiến độ được cập nhật khi có thay đổi.

## Giới hạn hoặc rủi ro

Nêu phần chưa triển khai và cách rollback nếu có.
