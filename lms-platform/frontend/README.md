# LMS frontend — portal tuần 5 (5.1–5.3)

Checkpoint 05/10/2026: Admin accounts/roles/permissions/reports; Instructor dashboard
và course/content builder CRUD/order/resources/completion gates; shared routing/forms/UI states.
Database chính **lms**, API **8002**, frontend **5173**. **11 unit, 7 browser E2E**, build đạt.
Hướng dẫn: [API/demo tuần 5](../docs/api/week-5.md), [review](../progress/week-5-review.md).

TypeScript + Vite, dùng shared transport types tại `../shared/contracts/api.ts`.
Node.js 24 được kiểm chứng local và dùng trong CI. Dependency được khóa trong package-lock.json.

## Chạy cùng backend demo

Terminal 1, từ thư mục gốc repository:

```powershell
cd lms-platform/backend
../../.venv/Scripts/python -m scripts.run_demo
```

Lệnh migrate/seed database `lms` bằng cấu hình MySQL trong backend/.env rồi mở API
tại http://127.0.0.1:8002. Dữ liệu được dùng xuyên suốt các tuần. Chỉ chạy seed ở development/test.

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

- `/login`, `/admin`, `/admin/users`, `/admin/reports`, `/instructor`, `/student`, `/courses/{id}` qua hash routes.
- Guard gọi `/auth/me` trước mỗi lần mở trang; role lấy từ server, không giải mã JWT
  để tự cấp quyền. Backend vẫn kiểm permission và resource scope ở mỗi API.
- Token chỉ ở bộ nhớ; không lưu localStorage/sessionStorage. Reload tab cần đăng nhập lại.
- 401: refresh rotation một lần, chia sẻ một promise giữa các request đồng thời,
  retry một lần; refresh thất bại thì xóa phiên và về đăng nhập.
- 403 giữ phiên và hiển thị từ chối quyền. Các lỗi có trace ID để tra cứu.
- Logout xóa state ngay và gọi revoke family; response cũ không khôi phục phiên sau logout.
- Nội dung từ API được gán qua textContent, không render HTML tùy ý.
- Có loading/empty/error/success, form chống submit lặp và layout cho desktop/mobile.
- Admin/Instructor có sửa/xóa/order metadata; file/link resources và completion gates.
- Tài khoản và report phân trang 10 mục; course quản lý 20 mục, tìm/lọc trong trang hiện tại.
  Student portal có dashboard/My Courses/lesson player; UI assignment/exam/grade thuộc WBS 5.5.

## Dữ liệu mẫu giao diện

Bản showcase dùng chung database `lms`, API cổng 8002 và frontend
cổng 5173. Từ thư mục `backend`, chạy:

```powershell
$env:LMS_DEMO_DATABASE = 'lms'
$env:LMS_DEMO_PORT = '8002'
../../.venv/Scripts/python -m scripts.run_demo
```

Từ thư mục `frontend`, chạy `npm run seed:demo`, rồi `npm run dev`.
Mở http://127.0.0.1:5173 và đăng nhập bằng `demo_student`, `demo_instructor`
hoặc `demo_admin`; mật khẩu mặc định `LmsDemo-Week2!2026`.

Bộ mẫu gồm 8 khóa học, 24 chương, 48 bài học, 16 bài tập và 3 bài nộp.
Có khóa học đang mở, bản nháp, lưu trữ; ghi danh đang học, chờ duyệt và tạm ngưng.
Script bỏ qua các mục đã tồn tại theo mã/tên, không xóa dữ liệu hiện có.
Chạy `node scripts/check-week5.mjs` khi hai server đang hoạt động để kiểm tra
Admin users/reports và Instructor dashboard/builder/desktop/mobile; ảnh lưu trong `.local-logs`.
Showcase cũ cổng 8004/5175 vẫn có thể chạy bằng `LMS_DEMO_PORT=8004`,
`LMS_API_BASE=http://127.0.0.1:8004/api/v1`, `npm run dev:demo` và `check-showcase.mjs`.

## Kiểm tra tự động

```powershell
npm test
npm run build
npx playwright install chromium
npm run test:e2e
```

11 unit tests cho API client/guard; 7 browser E2E tests dùng MySQL/API thật.
Riêng case error/loading/retry mô phỏng 503 và response chậm để kiểm tra UI.
E2E tự mở backend 8013/frontend 5174 và database riêng `lms_demo_e2e`.
DB này được giữ để debug; mỗi lần test dùng course code mới và seed idempotent.
Ảnh desktop/mobile được lưu tại `test-results/` (Git ignore).
CI dùng Python hệ thống qua `LMS_PYTHON=python`; local mặc định dùng `.venv` ở root.

`npm run build` tạo `dist/`. Khi triển khai, web server phải chuyển `/api` tới backend;
dev proxy của Vite không nằm trong bundle production. Bản này chưa cấu hình deployment production.

Tham khảo: [Vite server proxy](https://vite.dev/config/server-options),
[Playwright webServer](https://playwright.dev/docs/test-webserver).
