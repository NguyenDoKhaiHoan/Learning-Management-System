# LMS frontend — nền tảng tuần 2

TypeScript + Vite, dùng shared transport types tại `../shared/contracts/api.ts`.
Node.js 24 được kiểm chứng local và dùng trong CI. Dependency được khóa trong package-lock.json.

## Chạy cùng backend demo

Terminal 1, từ thư mục gốc repository:

```powershell
cd lms-platform/backend
../../.venv/Scripts/python -m scripts.run_demo
```

Lệnh tạo/migrate/seed riêng database `lms_demo_week2` bằng cấu hình kết nối MySQL hiện có
trong backend/.env rồi mở API tại http://127.0.0.1:8002. Không thay đổi database `lms`.
Tài khoản kết nối MySQL cần quyền tạo database demo. Chỉ chạy ở development/test.

Terminal 2, từ thư mục gốc repository:

```powershell
cd lms-platform/frontend
npm ci
npm run dev
```

Mở http://127.0.0.1:5173. Vite proxy `/api` tới API demo 8002, không cần cấu hình CORS.
Muốn dùng backend khác, đặt `$env:LMS_API_TARGET = 'http://127.0.0.1:8001'` trước khi chạy;
backend đó cần có code mới và tài khoản/permission phù hợp.

Demo account: `demo_admin`, `demo_instructor`, `demo_student`; mật khẩu mặc định chỉ dùng
trong database demo: `LmsDemo-Week2!2026`. Có thể đặt `LMS_DEMO_PASSWORD` trước khi tạo demo.
Seed từ chối ghi đè nếu account đã có mật khẩu/status khác. Không có public signup API.
Hướng dẫn đầy đủ: [demo tuần 2](../docs/api/week-2-demo.md).

## Phạm vi và bảo vệ phiên

- `/login`, `/admin`, `/instructor`, `/student`, `/courses/{id}` qua hash routes.
- Guard gọi `/auth/me` trước mỗi lần mở trang; role lấy từ server, không giải mã JWT
  để tự cấp quyền. Backend vẫn kiểm permission và resource scope ở mỗi API.
- Token chỉ ở bộ nhớ; không lưu localStorage/sessionStorage. Reload tab cần đăng nhập lại.
- 401: refresh rotation một lần, chia sẻ một promise giữa các request đồng thời,
  retry một lần; refresh thất bại thì xóa phiên và về đăng nhập.
- 403 giữ phiên và hiển thị từ chối quyền. Các lỗi có trace ID để tra cứu.
- Logout xóa state ngay và gọi revoke family; response cũ không khôi phục phiên sau logout.
- Nội dung từ API được gán qua textContent, không render HTML tùy ý.
- Có loading/empty/error/success, form chống submit lặp và layout cho desktop/mobile.
- Giao diện nền tảng phục vụ demo tạo/publish/ghi danh/duyệt/tạm ngưng; ordering,
  sửa/xóa metadata đầy đủ và một số thao tác quản trị vẫn dùng API/Postman.
- Danh sách demo tải tối đa 100 mục; pagination UI và portal đầy đủ còn thuộc các tuần sau.

## Kiểm tra

```powershell
npm test
npm run build
npx playwright install chromium
npm run test:e2e
```

11 unit tests cho API client/guard; 3 browser E2E tests gọi MySQL/API thật, không mock API.
E2E tự mở backend 8013/frontend 5174 và database riêng `lms_demo_e2e`.
DB này được giữ để debug; mỗi lần test dùng course code mới và seed idempotent.
Ảnh desktop/mobile được lưu tại `test-results/` (Git ignore).
CI dùng Python hệ thống qua `LMS_PYTHON=python`; local mặc định dùng `.venv` ở root.

`npm run build` tạo `dist/`. Khi triển khai, web server phải chuyển `/api` tới backend;
dev proxy của Vite không nằm trong bundle production. Bản này chưa cấu hình deployment production.

Tham khảo: [Vite server proxy](https://vite.dev/config/server-options),
[Playwright webServer](https://playwright.dev/docs/test-webserver).
