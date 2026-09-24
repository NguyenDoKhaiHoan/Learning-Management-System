# Đối chiếu tuần 3 — WBS 3.1–3.3

Checkpoint: 24/09/2026. Phạm vi này chỉ gồm ba task đầu tuần 3 trên Master Plan.

## 3.1 File metadata, upload và MIME/size validation

- Upload stream có giới hạn cấu hình, không giữ toàn bộ file trong RAM.
- Object key ngẫu nhiên, file nằm ở storage private; tên client chỉ là display name đã chuẩn hóa.
- Allowlist MIME và kiểm chữ ký/nội dung cho PDF/JPEG/PNG/MP4/UTF-8 text.
- Metadata gồm MIME, size, SHA-256, uploader; storage location không xuất hiện trong API.
- File và metadata được dọn khi transaction upload thất bại; upload/delete có audit.

## 3.2 Lesson access và lesson/resource API

- CRUD link/file resource theo đúng course → module → lesson boundary.
- Manager chỉ sửa resource khi course Draft.
- Student chỉ list/download khi course Published và enrollment Active.
- Download qua endpoint có authorization; không phát URL kho private.
- Kiểm thử gồm MIME giả, size quá giới hạn, path traversal tên file, link không phải file,
  course chưa publish và Student chưa enrollment.

## 3.3 lesson_progress, course_progress, completion_rules

- Migration tạo đủ ba bảng với FK, unique/check constraint và timestamp.
- Completion rule mặc định 100%, manager cấu hình trong Course Draft.
- Lesson status và vị trí chỉ tăng; `COMPLETED` không thể quay lại.
- Cập nhật lesson, course aggregate và audit trong cùng transaction.
- API `progress/me` trả completed/total/percent/completed_at theo enrollment hiện tại.

## Bằng chứng kiểm thử

- Ruff: đạt.
- Unit backend: 46 test đạt.
- Acceptance WBS 3.1–3.3 trên MySQL thật: 2 test đạt.
- Toàn bộ backend regression trên MySQL thật: 65 test đạt, không skip; gồm migration
  upgrade → downgrade → upgrade.
- OpenAPI đã export và contract drift check đạt.

Google Sheet chưa được ghi trong lần triển khai này. `tasks.json` là checkpoint local; chỉ chạy
preview/`--apply` khi có yêu cầu đồng bộ riêng.
