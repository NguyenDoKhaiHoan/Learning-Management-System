# Ma trận quyền nghiệp vụ

Backend lấy role và permission từ database ở mỗi request. Claim tùy ý trong JWT không
cấp thêm quyền. Resource scope luôn được kiểm tra sau role check.

| Hành động | Admin | Instructor | Student |
| --- | --- | --- | --- |
| Quản lý account/role/permission | Có | Không | Không |
| Tạo/sửa course và content | Có | Course sở hữu hoặc được staff | Không |
| Publish course/exam/assignment | Có | Course sở hữu hoặc được staff | Không |
| Duyệt/tạm ngưng enrollment | Có | Course sở hữu hoặc được staff | Gửi request của chính mình |
| Học lesson và cập nhật progress | Theo quyền quản trị | Theo quyền staff | Chỉ enrollment ACTIVE + course PUBLISHED |
| Tạo attempt/nộp bài | Theo quyền quản trị | Không thay student | Chỉ attempt/submission của chính mình |
| Chấm/publish/revise grade | Có | Course scope | Chỉ đọc grade Published của mình |
| Forum và notification | Theo scope quản trị | Course scope + moderation | Course membership; chỉ sửa trạng thái của mình |
| Audit/security/report/export | Toàn hệ thống | Course/report scope | Không |

Các điều kiện từ chối phải không tạo side effect nghiệp vụ. Draft/Archived course,
enrollment PENDING/SUSPENDED, account LOCKED/INACTIVE và file ngoài parent scope đều
bị chặn. Private file/CSV không trả đường dẫn filesystem và luôn re-check status,
containment, digest và authorization lúc download.
