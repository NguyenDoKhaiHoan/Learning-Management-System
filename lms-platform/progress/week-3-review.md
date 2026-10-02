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

## Rà soát 02/10/2026 — WBS 3.4–3.8

- **3.4:** completion rule và aggregate lesson/assignment tính trong cùng transaction;
  state/position không lùi; test hoàn thành lesson → nộp bài → progress 50% → 100% đạt.
- **3.5:** assignment create/list/detail/update/delete Draft, publish/close/archive,
  cửa sổ mở/deadline và allow_late/late_until; manager trên Course Published; scope guard.
- **3.6:** bài nộp text/file có version mới bất biến, submitted_at/status/submitted_by,
  MIME/size/private storage; request đồng thời không vượt attempt limit.
- **3.7:** manager xem submission/file trong course của mình; Student chỉ xem bài của
  mình; user ngoài course/enrollment suspended bị chặn; rollback khi audit lỗi.
- **3.8:** 5 MySQL assignment acceptance gồm lifecycle, version/late/file, deadline/
  rollback, cạnh tranh attempt và demo learning → submission → progress.
  Đã bổ sung hướng dẫn demo chạy lại tại docs/api/week-3.md.

Full backend regression **87 passed** trên MySQL thật, không skip; frontend **11 unit**,
**3 browser E2E** và build đạt. Sau đó thêm 2 case concurrency grading, tổng 89 test
backend khác nhau đã đạt. Chi tiết môi trường tại week-4-grading-review.md.
WBS 3.4–3.8 được bổ sung tracking đúng tên trên Master Plan để đồng bộ F/G theo yêu cầu.
