# Shared API v1 contracts

Backend `src/core/contracts.py` là nguồn chuẩn. `api.ts` là kiểu transport để frontend
import; JSON Schema và OpenAPI là artifact sinh tự động cho kiểm tra contract.
IDs BIGINT đi qua JSON dưới dạng string để không mất độ chính xác trong JavaScript.

Từ repository root:

```powershell
.venv/Scripts/python lms-platform/backend/scripts/export_contracts.py
.venv/Scripts/python lms-platform/backend/scripts/export_contracts.py --check
```

`--check` dùng trong CI để chặn schema drift. Khi đổi response, cập nhật `api.ts`,
sinh lại JSON và review diff cùng PR. Các frontend features phải tái sử dụng các kiểu
này thay vì tự đổi tên trường. API error code không dựa vào nội dung message.
401 có `WWW-Authenticate: Bearer`; 403 nghĩa token hợp lệ nhưng không đủ role.
`X-Trace-ID` khớp body `trace_id` kể cả lỗi. `/healthz` và `/livez` dùng success envelope;
readiness thất bại trả ErrorResponse 503.

Token access skeleton không có endpoint phát hành công khai; helper chỉ được gọi
sau khi login use case xác minh mật khẩu (tuần 2). Không dùng role client gửi lên.
