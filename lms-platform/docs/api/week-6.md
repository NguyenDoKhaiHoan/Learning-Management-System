# Tuần 6 — WBS 6.1–6.3

## 6.1 Audit trail

Các thay đổi course/assignment/exam publication, role/permission, grade draft/publish/revise,
assignment submission và exam submit/auto-submit ghi audit cùng transaction nghiệp vụ.
Audit lỗi thì thay đổi nghiệp vụ rollback. Grade history giữ snapshot từng version;
audit grade chứa score/max_score/status/version và reason điều chỉnh. Submission audit
chứa course/enrollment/assignment/version/type; không lưu nội dung bài hoặc credentials.

`GET /api/v1/audit/logs` chỉ dành cho Admin. Có filter actor_id/action/resource/resource_id/
trace_id/since/until, limit 1–100 và offset ≥0; trả items/total/limit/offset. ID là chuỗi,
sắp xếp timestamp/id giảm dần. Thời gian không có timezone hiểu là UTC. Không có API sửa/xóa log.
UI `#/admin/audit` hỗ trợ lọc và phân trang, route guard cùng backend authorization.

Kiểm chứng: `tests/integration/test_week6_audit.py` và regression tuần 3/4/5.
