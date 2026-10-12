# Review tuần 6 — 12/10/2026

## WBS 6.1 — hoàn thành

- Publish course/assignment/exam, role/permission, grade draft/publish/revise,
  assignment text/file và exam submit/auto-submit ghi audit trong transaction nghiệp vụ.
- Audit chứa actor/resource/trace/timestamp và ngữ cảnh phiên bản/trạng thái/điểm;
  không ghi credentials hoặc nội dung bài nộp. Grade history giữ snapshot các version.
- Admin có API/trang nhật ký với filter và pagination; Student/Instructor không truy cập.
- 25 MySQL tests audit/assignment/grading/portal đạt, gồm rollback publish/permission/role,
  submission, grade publication và exam grading khi audit lỗi. Browser acceptance Admin
  lọc log, empty state và Student guard đạt. Frontend build, Ruff và export contracts đạt.

Chi tiết contract: [docs/api/week-6.md](../docs/api/week-6.md).
Chỉ cập nhật WBS 6.1–6.3 khi có bằng chứng cho từng mục; không đánh dấu 6.4–6.8.
