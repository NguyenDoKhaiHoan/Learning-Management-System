// Populate only the dedicated local demo API. Existing courses are preserved.
const base = "http://127.0.0.1:8004/api/v1";
const password = process.env.LMS_DEMO_PASSWORD ?? "LmsDemo-Week2!2026";
async function request(token, path, method = "GET", data) {
  const response = await fetch(base + path, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: data === undefined ? undefined : JSON.stringify(data),
    signal: AbortSignal.timeout(15000),
  });
  const result = await response.json();
  if (!response.ok)
    throw new Error(`${method} ${path}: ${response.status} ${result.message}`);
  return result.data;
}
async function login(name) {
  const auth = await request(null, "/auth/login", "POST", {
    login: name,
    password,
  });
  return auth.access_token;
}

const samples = [
  {
    code: "WEB_101",
    title: "Lập trình web từ nền tảng",
    description:
      "Xây dựng website đầu tiên với HTML, CSS và JavaScript. Thực hành bố cục responsive và hoàn thiện trang portfolio cá nhân.",
    topics: [
      "Cấu trúc trang HTML",
      "Bố cục CSS và responsive",
      "Tương tác với JavaScript",
    ],
    task: "Xây dựng trang giới thiệu bản thân",
    status: "PUBLISHED",
    enrollment: "ACTIVE",
    done: 2,
  },
  {
    code: "UX_201",
    title: "Thiết kế UI/UX cho sản phẩm số",
    description:
      "Từ nghiên cứu người dùng đến wireframe và prototype. Thiết kế một trải nghiệm đặt lịch rõ ràng, dễ tiếp cận và nhất quán.",
    topics: [
      "Nghiên cứu người dùng",
      "Wireframe và luồng thao tác",
      "Prototype và kiểm thử",
    ],
    task: "Thiết kế luồng đặt lịch học",
    status: "PUBLISHED",
    enrollment: "ACTIVE",
    done: 1,
  },
  {
    code: "PY_101",
    title: "Python cho người mới bắt đầu",
    description:
      "Làm quen tư duy lập trình qua các ví dụ gần gũi. Sử dụng biến, vòng lặp, hàm và tệp dữ liệu để tự động hóa công việc.",
    topics: [
      "Biến và kiểu dữ liệu",
      "Điều kiện và vòng lặp",
      "Hàm và xử lý tệp",
    ],
    task: "Viết chương trình quản lý chi tiêu",
    status: "PUBLISHED",
    enrollment: "PENDING",
    done: 0,
  },
  {
    code: "DATA_201",
    title: "Phân tích dữ liệu với SQL",
    description:
      "Đọc hiểu dữ liệu, viết truy vấn và kết hợp nhiều bảng. Khám phá các chỉ số kinh doanh qua một bộ dữ liệu bán hàng mẫu.",
    topics: [
      "Truy vấn và lọc dữ liệu",
      "Kết hợp bảng với JOIN",
      "Tổng hợp và báo cáo",
    ],
    task: "Phân tích doanh thu theo tháng",
    status: "PUBLISHED",
    enrollment: "ACTIVE",
    done: 3,
  },
  {
    code: "PM_101",
    title: "Quản lý dự án theo Agile",
    description:
      "Lập kế hoạch sprint, xây dựng backlog và phối hợp nhóm hiệu quả. Thực hành quản lý một dự án sản phẩm từ ý tưởng đến bàn giao.",
    topics: [
      "Nguyên tắc Agile",
      "Backlog và lập kế hoạch sprint",
      "Review và cải tiến",
    ],
    task: "Lập kế hoạch sprint đầu tiên",
    status: "PUBLISHED",
    enrollment: null,
    done: 0,
  },
  {
    code: "ENG_201",
    title: "Tiếng Anh trong công việc",
    description:
      "Tự tin viết email, tham gia cuộc họp và trình bày ý tưởng. Luyện tập qua các tình huống giao tiếp thực tế tại nơi làm việc.",
    topics: [
      "Email chuyên nghiệp",
      "Giao tiếp trong cuộc họp",
      "Trình bày ý tưởng",
    ],
    task: "Viết email đề xuất kế hoạch làm việc",
    status: "PUBLISHED",
    enrollment: "SUSPENDED",
    done: 0,
  },
  {
    code: "REACT_301",
    title: "Xây dựng ứng dụng với React",
    description:
      "Phát triển ứng dụng theo component, quản lý state và kết nối API. Dự án thực hành: bảng quản lý công việc cho nhóm.",
    topics: ["Component và props", "State và sự kiện", "Kết nối API"],
    task: "Xây dựng bảng quản lý công việc",
    status: "DRAFT",
    enrollment: null,
    done: 0,
  },
  {
    code: "GIT_101",
    title: "Git và quy trình làm việc nhóm",
    description:
      "Quản lý phiên bản, phối hợp qua nhánh và review mã nguồn. Tài liệu của khóa học đã kết thúc, được lưu để tham khảo.",
    topics: [
      "Commit và lịch sử thay đổi",
      "Nhánh và hợp nhất",
      "Pull request và code review",
    ],
    task: "Thực hành quy trình pull request",
    status: "ARCHIVED",
    enrollment: null,
    done: 0,
  },
];

const instructor = await login("demo_instructor");
const student = await login("demo_student");
const currentStudent = await request(student, "/auth/me");
const existing = await request(instructor, "/courses?limit=100");
const enrollmentList = await request(student, "/enrollments/me?limit=100");
const now = Date.now();
const date = (days) => new Date(now + days * 86400000).toISOString();

for (const sample of samples) {
  const code = `SHOWCASE_${sample.code}`;
  let course = existing.find((item) => item.code === code);
  if (!course)
    course = await request(instructor, "/courses", "POST", {
      code,
      title: sample.title,
      description: sample.description,
    });
  const path = `/courses/${course.id}`;
  const modules = await request(instructor, `${path}/modules`);
  const lessonIds = [];
  for (const [index, topic] of sample.topics.entries()) {
    const title = `Chương ${index + 1}: ${topic}`;
    let module = modules.find((item) => item.title === title);
    if (!module && course.status === "DRAFT")
      module = await request(instructor, `${path}/modules`, "POST", { title });
    if (!module) continue;
    const lessons = module.lessons ?? [];
    for (const [offset, lessonTitle] of [
      `${topic}: kiến thức cốt lõi`,
      `Thực hành: ${topic.toLocaleLowerCase("vi")}`,
    ].entries()) {
      let lesson = lessons.find((item) => item.title === lessonTitle);
      if (!lesson && course.status === "DRAFT") {
        lesson = await request(
          instructor,
          `${path}/modules/${module.id}/lessons`,
          "POST",
          {
            title: lessonTitle,
            lesson_type: "ARTICLE",
            is_preview: index === 0 && offset === 0,
            content: `${lessonTitle}\n\nMục tiêu\nSau bài học, bạn có thể giải thích ${topic.toLocaleLowerCase("vi")} và áp dụng vào dự án ${sample.title.toLocaleLowerCase("vi")}.\n\nNội dung\n1. Xác định mục tiêu và yêu cầu của bài toán.\n2. Chia công việc thành những bước nhỏ có thể kiểm chứng.\n3. Thực hành với một ví dụ, ghi lại kết quả và những điểm cần cải thiện.\n\nBài thực hành\n${sample.task}. Hãy mô tả cách tiếp cận, kết quả và một điều bạn rút ra sau khi thực hiện.\n\nTự đánh giá\nBạn đã giải thích được lựa chọn của mình chưa? Hãy kiểm tra kết quả trước khi đánh dấu hoàn thành.`,
          },
        );
      }
      if (lesson) lessonIds.push(lesson.id);
    }
  }
  if (course.status === "DRAFT") {
    await request(instructor, `${path}/completion-rule`, "PUT", {
      required_lesson_percent: 100,
      require_submitted_assignments: true,
    });
    if (sample.status !== "DRAFT")
      course = await request(instructor, `${path}/status`, "POST", {
        status: "PUBLISHED",
      });
  }
  if (course.status !== "ARCHIVED") {
    const assignments = await request(instructor, `${path}/assignments`);
    for (const [index, title] of [
      sample.task,
      `Tổng kết: ${sample.title}`,
    ].entries()) {
      let assignment = assignments.find((item) => item.title === title);
      if (!assignment)
        assignment = await request(instructor, `${path}/assignments`, "POST", {
          title,
          description: `${index === 0 ? "Vận dụng kiến thức đã học để hoàn thành sản phẩm thực hành." : "Tóm tắt kiến thức và tự đánh giá kết quả học tập."}\nYêu cầu: trình bày mục tiêu, các bước thực hiện và kết quả. Nộp nội dung trực tiếp hoặc tệp PDF.`,
          opens_at: date(-7),
          due_at: date(7 + index * 7),
          allow_late: true,
          late_until: date(10 + index * 7),
          max_attempts: 3,
          max_file_bytes: 10485760,
          allowed_mime_types: ["application/pdf"],
          max_score: 100,
        });
      if (course.status === "PUBLISHED" && assignment.status === "DRAFT")
        await request(
          instructor,
          `${path}/assignments/${assignment.id}/status`,
          "POST",
          { status: "PUBLISHED" },
        );
    }
  }
  if (sample.status === "ARCHIVED" && course.status !== "ARCHIVED")
    await request(instructor, `${path}/status`, "POST", { status: "ARCHIVED" });
  if (
    sample.enrollment &&
    !enrollmentList.some((item) => item.course_id === course.id)
  ) {
    await request(student, `${path}/enrollments`, "POST", {});
    if (sample.enrollment !== "PENDING") {
      await request(
        instructor,
        `${path}/enrollments/${currentStudent.id}`,
        "PATCH",
        { status: "ACTIVE" },
      );
      for (const lessonId of lessonIds.slice(0, sample.done))
        await request(student, `${path}/lessons/${lessonId}/progress`, "PUT", {
          status: "COMPLETED",
          last_position_seconds: 0,
        });
      if (sample.done > 0) {
        const assignments = await request(student, `${path}/assignments`);
        await request(
          student,
          `${path}/assignments/${assignments[0].id}/submissions`,
          "POST",
          {
            answer_text: `Bài thực hành: ${sample.task}\n\nEm đã hoàn thành bản đầu tiên theo yêu cầu, kiểm tra kết quả và ghi nhận phản hồi. Phần cần cải thiện tiếp theo là bổ sung các trường hợp đặc biệt và trình bày kết quả rõ ràng hơn.`,
          },
        );
      }
      if (sample.enrollment === "SUSPENDED")
        await request(
          instructor,
          `${path}/enrollments/${currentStudent.id}`,
          "PATCH",
          { status: "SUSPENDED" },
        );
    }
  }
  console.log(`${code}: ${sample.title}`);
}
console.log(
  "Showcase ready at http://127.0.0.1:5175. Log in with demo_student, demo_instructor or demo_admin.",
);
