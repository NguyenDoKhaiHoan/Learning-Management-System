"""Original Vietnamese teaching material based on the linked primary references.

These are local LMS courses and practice assessments, not courses or official
certification exams offered by the referenced publishers. People and activity
fixtures are synthetic. Course duration is an internal teaching estimate.
"""

# ruff: noqa: E501 -- keep the reviewed Vietnamese teaching text readable as sentences.

from dataclasses import dataclass


@dataclass(frozen=True)
class Question:
    topic: str
    prompt: str
    correct: str
    wrong: tuple[str, str]
    explanation: str


@dataclass(frozen=True)
class Course:
    title: str
    source_title: str
    source_url: str
    prerequisite: str
    assignment: str
    questions: tuple[Question, ...]


COURSES = (
    Course(
        "Lập trình Python nền tảng",
        "Python Tutorial",
        "https://docs.python.org/3/tutorial/",
        "Biết sử dụng máy tính và trình soạn thảo.",
        "Viết hàm thống kê số lần xuất hiện của từng từ; kiểm tra chuỗi rỗng, Unicode và từ lặp.",
        (
            Question(
                "List và tuple",
                "Trong Python, kiểu nào cho phép thêm phần tử bằng append()?",
                "list",
                ("tuple", "str"),
                "List là dãy có thể thay đổi. Tuple và chuỗi không có phương thức append().",
            ),
            Question(
                "Hàm và giá trị trả về",
                "Một hàm Python chạy hết mà không thực hiện return sẽ trả gì?",
                "None",
                ("0 trong mọi trường hợp", "Một danh sách rỗng"),
                "Khi không có biểu thức return được thực hiện, hàm trả về None.",
            ),
            Question(
                "Dictionary",
                "Biểu thức {'x': 3}.get('y', 0) trả về gì?",
                "0",
                ("3", "Luôn phát sinh KeyError"),
                "dict.get trả giá trị mặc định khi khóa không tồn tại; ở đây mặc định là 0.",
            ),
        ),
    ),
    Course(
        "SQL và thiết kế cơ sở dữ liệu",
        "MySQL 8.0 Tutorial",
        "https://docs.oracle.com/cd/E17952_01/mysql-8.0-en/tutorial.html",
        "Hiểu bảng, hàng và cột.",
        "Thiết kế users, courses và enrollments; đặt khóa ngoại và UNIQUE(student_id, course_id).",
        (
            Question(
                "Lọc dữ liệu",
                "Mệnh đề nào lọc hàng theo điều kiện trước khi GROUP BY?",
                "WHERE",
                ("ORDER BY", "HAVING"),
                "WHERE lọc các hàng đầu vào; HAVING lọc các nhóm sau khi tổng hợp.",
            ),
            Question(
                "NULL",
                "Trong SQL, điều kiện nào kiểm tra email chưa có giá trị?",
                "email IS NULL",
                ("email = NULL", "email = 'NULL'"),
                "NULL biểu diễn giá trị thiếu; dùng IS NULL thay cho phép so sánh bằng.",
            ),
            Question(
                "Khóa và tính duy nhất",
                "Ràng buộc nào chặn hai ghi danh trùng cùng học viên và khóa học?",
                "UNIQUE(student_id, course_id)",
                ("INDEX(student_id) thông thường", "ORDER BY course_id"),
                "Unique key trên cặp cột ngăn hai hàng có cùng cặp giá trị không NULL.",
            ),
        ),
    ),
    Course(
        "Phát triển Web hiện đại",
        "MDN: Learn web development",
        "https://developer.mozilla.org/en-US/docs/Learn_web_development",
        "Biết thao tác tệp văn bản.",
        "Tạo trang giới thiệu khóa học bằng HTML có ngữ nghĩa, CSS responsive và form có nhãn.",
        (
            Question(
                "HTML có ngữ nghĩa",
                "Phần tử HTML nào tạo liên kết điều hướng tới một URL?",
                '<a href="...">',
                ('<div href="...">', '<span src="...">'),
                "Phần tử a cùng thuộc tính href tạo hyperlink; div và span không tự tạo liên kết.",
            ),
            Question(
                "CSS",
                "Thuộc tính CSS nào thay đổi màu chữ của phần tử?",
                "color",
                ("background-color", "font-size"),
                "color đặt màu foreground của văn bản; background-color đặt màu nền.",
            ),
            Question(
                "JavaScript và DOM",
                "API nào tìm phần tử đầu tiên khớp CSS selector trong document?",
                "document.querySelector()",
                ("document.createElement()", "JSON.parse()"),
                "querySelector trả phần tử khớp đầu tiên hoặc null nếu không tìm thấy.",
            ),
        ),
    ),
    Course(
        "Git và quy trình phát triển nhóm",
        "Git tutorial",
        "https://git-scm.com/docs/gittutorial",
        "Biết sử dụng terminal ở mức cơ bản.",
        "Tạo branch, thực hiện hai commit, giải quyết một xung đột và mô tả thay đổi để review.",
        (
            Question(
                "Staging area",
                "Lệnh nào đưa thay đổi của README.md vào staging area?",
                "git add README.md",
                ("git push README.md", "git log README.md"),
                "git add cập nhật index; commit tiếp theo lấy nội dung từ index.",
            ),
            Question(
                "Commit",
                "git commit ghi nhận nội dung nào?",
                "Snapshot của các thay đổi đã stage trong index",
                ("Mọi tệp trên máy", "Chỉ lịch sử remote"),
                "Commit tạo snapshot từ index, nên thay đổi chưa stage không tự xuất hiện trong commit.",
            ),
            Question(
                "Remote",
                "Lệnh nào tải các ref và object mới từ remote mà không tự merge vào nhánh hiện tại?",
                "git fetch",
                ("git add", "git commit"),
                "fetch cập nhật thông tin remote; nó không tự hợp nhất vào working branch.",
            ),
        ),
    ),
    Course(
        "Docker và môi trường reproducible",
        "Docker: Get started",
        "https://docs.docker.com/get-started/",
        "Biết chạy ứng dụng từ terminal.",
        "Viết Dockerfile và Compose cho API; dùng volume cho dữ liệu và healthcheck cho dịch vụ.",
        (
            Question(
                "Image và container",
                "Container Docker đang chạy được tạo từ đối tượng nào?",
                "Image",
                ("Một Git branch bắt buộc", "Một file CSV"),
                "Image là mẫu đóng gói; container là instance được tạo từ image cùng cấu hình chạy.",
            ),
            Question(
                "Lưu trữ",
                "Cách nào giữ dữ liệu độc lập với vòng đời một container?",
                "Dùng named volume hoặc bind mount phù hợp",
                ("Chỉ ghi vào writable layer rồi xóa container", "Đặt dữ liệu trong tên container"),
                "Volume và bind mount lưu dữ liệu ngoài writable layer có thể bị mất khi container bị xóa.",
            ),
            Question(
                "Compose",
                "Docker Compose dùng để làm gì?",
                "Khai báo và chạy ứng dụng gồm nhiều service",
                ("Thay thế toàn bộ hệ điều hành host", "Tự động kiểm chứng mọi lỗ hổng ứng dụng"),
                "Compose mô tả service, network và volume rồi quản lý chúng như một ứng dụng.",
            ),
        ),
    ),
    Course(
        "Thiết kế API HTTP",
        "RFC 9110: HTTP Semantics",
        "https://www.rfc-editor.org/rfc/rfc9110.html",
        "Hiểu client, server và JSON.",
        "Thiết kế API khóa học: resource URL, method, status, pagination và mẫu lỗi có trace ID.",
        (
            Question(
                "GET",
                "Theo ngữ nghĩa HTTP, GET thuộc nhóm phương thức nào?",
                "Safe và idempotent",
                ("Luôn thay đổi trạng thái nghiệp vụ", "Chỉ dành cho upload tệp"),
                "GET được định nghĩa là safe và idempotent; không nên dùng GET để yêu cầu thay đổi nghiệp vụ.",
            ),
            Question(
                "201 Created",
                "Mã trạng thái nào thể hiện request thành công và tạo tài nguyên mới?",
                "201",
                ("404", "500"),
                "201 Created báo đã tạo tài nguyên; 404 và 500 lần lượt là lỗi không tìm thấy và lỗi server.",
            ),
            Question(
                "401 và 403",
                "Mã 401 thường yêu cầu client xử lý điều gì?",
                "Cung cấp thông tin xác thực hợp lệ",
                ("Xóa tài nguyên đã tạo", "Nén request thành ZIP"),
                "401 Unauthorized cho biết request thiếu thông tin xác thực hợp lệ và đi với challenge phù hợp.",
            ),
        ),
    ),
    Course(
        "Kiểm thử phần mềm với pytest",
        "pytest: How to write and report assertions",
        "https://docs.pytest.org/en/stable/how-to/assert.html",
        "Biết hàm và exception trong Python.",
        "Viết test hàm tính điểm: trường hợp đúng, biên, đầu vào sai và exception; chạy pytest.",
        (
            Question(
                "Assertion",
                "Trong pytest, câu lệnh Python nào thường dùng để kiểm tra kết quả?",
                "assert",
                ("print thay cho mọi kiểm tra", "pass"),
                "pytest hỗ trợ assert thông thường và hiển thị thông tin giá trị khi assertion thất bại.",
            ),
            Question(
                "Exception",
                "Công cụ nào xác nhận một đoạn mã phát sinh ValueError?",
                "with pytest.raises(ValueError):",
                ("with pytest.ignore_all():", "assert print(ValueError)"),
                "pytest.raises kiểm tra exception mong đợi trong một context manager.",
            ),
            Question(
                "Kiểm tra đầu ra",
                "assert result == 5 sẽ thất bại khi result là giá trị nào?",
                "4",
                ("5", "5.0"),
                "4 không bằng 5. Trong Python, 5 và 5.0 so sánh bằng với toán tử ==.",
            ),
        ),
    ),
    Course(
        "An toàn ứng dụng Web",
        "OWASP Authorization Cheat Sheet",
        "https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html",
        "Hiểu HTTP và đăng nhập.",
        "Viết ma trận quyền và test đổi ID tài nguyên để chứng minh backend chặn truy cập chéo người dùng.",
        (
            Question(
                "Xác thực và phân quyền",
                "Authorization quyết định điều gì?",
                "Người dùng có được thực hiện thao tác trên tài nguyên cụ thể hay không",
                ("Màu giao diện đăng nhập", "Tốc độ nén tệp"),
                "Authentication xác minh danh tính; authorization kiểm tra quyền với hành động và tài nguyên.",
            ),
            Question(
                "Kiểm tra quyền",
                "Backend nên kiểm tra quyền ở thời điểm nào?",
                "Trên mỗi request cần bảo vệ",
                ("Chỉ khi hiển thị nút trong frontend", "Chỉ khi tạo tài khoản"),
                "Kiểm tra quyền mỗi request giúp ngăn client bỏ qua UI hoặc dùng ID tài nguyên của người khác.",
            ),
            Question(
                "Deny by default",
                "Nếu không tìm thấy quy tắc cho phép truy cập, nên xử lý thế nào?",
                "Từ chối truy cập",
                ("Cho phép mọi tài nguyên", "Tin role do client tự gửi"),
                "Deny by default yêu cầu quyền truy cập được cho phép rõ ràng thay vì tự mở khi thiếu cấu hình.",
            ),
        ),
    ),
    Course(
        "Cấu trúc dữ liệu",
        "Python Tutorial: Data Structures",
        "https://docs.python.org/3/tutorial/datastructures.html",
        "Biết vòng lặp và hàm.",
        "Cài đặt stack và queue; mô tả thao tác, kiểm tra rỗng và lựa chọn cấu trúc cho lịch sử undo.",
        (
            Question(
                "Stack",
                "Stack lấy phần tử theo nguyên tắc nào?",
                "LIFO: vào sau, ra trước",
                ("FIFO: vào trước, ra trước", "Luôn chọn giá trị lớn nhất"),
                "Stack thêm và lấy ở cùng một đầu, nên phần tử vào sau được lấy trước.",
            ),
            Question(
                "Queue",
                "Queue thông thường xử lý phần tử theo nguyên tắc nào?",
                "FIFO: vào trước, ra trước",
                ("LIFO: vào sau, ra trước", "Chỉ lấy phần tử ở giữa"),
                "Queue thêm ở đuôi và lấy ở đầu để giữ thứ tự đến trước được phục vụ trước.",
            ),
            Question(
                "Ứng dụng stack",
                "Cấu trúc nào phù hợp để lưu các thao tác cho chức năng undo tuần tự?",
                "Stack",
                ("Một biến boolean duy nhất", "Bộ sinh số ngẫu nhiên"),
                "Undo đảo thao tác gần nhất trước, khớp với thứ tự LIFO của stack.",
            ),
        ),
    ),
    Course(
        "Giải thuật và độ phức tạp",
        "Python bisect: Array bisection algorithm",
        "https://docs.python.org/3/library/bisect.html",
        "Biết mảng, vòng lặp và điều kiện.",
        "So sánh tìm tuyến tính và tìm nhị phân trên danh sách đã sắp xếp; đếm số phép so sánh.",
        (
            Question(
                "Tìm tuyến tính",
                "Tìm tuyến tính trên n phần tử có độ phức tạp thời gian xấu nhất nào?",
                "O(n)",
                ("O(1) trong mọi trường hợp", "O(log n) trong mọi trường hợp"),
                "Khi phần tử ở cuối hoặc không có, tìm tuyến tính có thể phải kiểm tra toàn bộ n phần tử.",
            ),
            Question(
                "Tìm nhị phân",
                "Điều kiện quan trọng để dùng tìm nhị phân trên mảng là gì?",
                "Mảng đã được sắp xếp theo quan hệ so sánh dùng khi tìm",
                ("Mảng phải có số phần tử chẵn", "Mọi phần tử phải bằng nhau"),
                "Tìm nhị phân loại bỏ một nửa miền tìm dựa vào thứ tự của mảng.",
            ),
            Question(
                "Chia đôi miền tìm",
                "Tìm nhị phân có số bước so sánh xấu nhất tăng theo bậc nào?",
                "O(log n)",
                ("O(n squared)", "O(n factorial)"),
                "Miền tìm được chia đôi sau mỗi bước nên số bước tăng theo logarit của kích thước đầu vào.",
            ),
        ),
    ),
    Course(
        "Phân tích dữ liệu với pandas",
        "pandas: Introductory tutorials",
        "https://pandas.pydata.org/docs/getting_started/intro_tutorials/",
        "Biết Python cơ bản.",
        "Đọc CSV điểm học viên, kiểm tra dữ liệu thiếu, tính trung bình theo khóa học và ghi rõ giả định.",
        (
            Question(
                "DataFrame",
                "DataFrame trong pandas mô tả cấu trúc nào?",
                "Bảng hai chiều có nhãn hàng và cột",
                ("Chỉ một số nguyên", "Một ảnh bitmap bắt buộc"),
                "DataFrame lưu dữ liệu dạng bảng với các hàng và cột có nhãn.",
            ),
            Question(
                "Đọc CSV",
                "Hàm pandas nào đọc tệp CSV thành DataFrame?",
                "pd.read_csv()",
                ("pd.draw_csv()", "pd.execute_html()"),
                "read_csv phân tích dữ liệu văn bản phân cách thành bảng.",
            ),
            Question(
                "Dữ liệu thiếu",
                "Phương thức nào tạo mặt nạ kiểm tra giá trị thiếu?",
                "isna()",
                ("sort_values()", "rename()"),
                "isna trả về boolean tương ứng với vị trí thiếu; sắp xếp hay đổi tên không thay cho kiểm tra thiếu.",
            ),
        ),
    ),
    Course(
        "Nhập môn học máy",
        "scikit-learn: Common pitfalls",
        "https://scikit-learn.org/stable/common_pitfalls.html",
        "Biết Python và thống kê mô tả.",
        "Chia train/test trước khi fit preprocessing; dùng pipeline và báo cáo metric trên test chưa sử dụng.",
        (
            Question(
                "Data leakage",
                "Fit scaler trên cả train và test trước khi đánh giá có rủi ro gì?",
                "Rò rỉ thông tin từ test vào quy trình huấn luyện",
                ("Luôn đảm bảo đánh giá khách quan hơn", "Tự động loại bỏ overfitting"),
                "Tham số tiền xử lý phải học từ train để test mô phỏng dữ liệu chưa thấy.",
            ),
            Question(
                "Pipeline",
                "Pipeline giúp tránh leakage bằng cách nào khi dùng đúng?",
                "Fit preprocessing cùng estimator chỉ trên tập huấn luyện của từng lượt",
                ("Xóa toàn bộ test labels", "Thay tất cả metric bằng accuracy"),
                "Pipeline gộp các bước biến đổi và estimator trong cùng quy trình fit của train fold.",
            ),
            Question(
                "Đánh giá",
                "Tập test cuối cùng nên được dùng như thế nào?",
                "Đánh giá khả năng tổng quát sau khi chốt lựa chọn mô hình",
                ("Liên tục dùng để điều chỉnh mọi tham số", "Thay cho toàn bộ dữ liệu huấn luyện"),
                "Dùng test lặp lại để lựa chọn mô hình có thể làm sai lệch kết quả đánh giá cuối.",
            ),
        ),
    ),
    Course(
        "Điện toán đám mây căn bản",
        "AWS IAM: Security best practices",
        "https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html",
        "Hiểu server, mạng và tài khoản.",
        "Thiết kế quyền tối thiểu cho ứng dụng chỉ cần đọc một vùng lưu trữ; mô tả credential tạm thời.",
        (
            Question(
                "Least privilege",
                "Nguyên tắc least privilege cấp quyền như thế nào?",
                "Chỉ quyền cần để thực hiện công việc",
                ("Administrator cho mọi workload", "Mọi action trên mọi resource"),
                "Quyền tối thiểu giới hạn action, resource và điều kiện theo nhu cầu thực tế.",
            ),
            Question(
                "Credential workload",
                "Đối với workload hỗ trợ IAM role, nên ưu tiên credential nào?",
                "Credential tạm thời qua role phù hợp",
                ("Root access key commit trong Git", "Password dùng chung trong mã nguồn"),
                "Role và credential tạm thời giảm nhu cầu quản lý access key dài hạn trong ứng dụng.",
            ),
            Question(
                "MFA",
                "MFA bổ sung điều gì cho quá trình đăng nhập?",
                "Một yếu tố xác thực bổ sung ngoài password",
                ("Quyền quản trị tự động", "Bỏ yêu cầu quản lý quyền"),
                "MFA tăng bảo vệ danh tính; nó không thay cho authorization hay nguyên tắc quyền tối thiểu.",
            ),
        ),
    ),
    Course(
        "DevOps và CI/CD",
        "GitHub Actions: Understanding workflows",
        "https://docs.github.com/en/actions/get-started/understand-github-actions",
        "Biết Git và cách chạy test.",
        "Tạo workflow gồm lint, test và build; chỉ cho bước phụ thuộc chạy khi các bước trước thành công.",
        (
            Question(
                "Workflow",
                "Workflow GitHub Actions thường được khai báo bằng định dạng nào?",
                "YAML trong .github/workflows",
                ("Chỉ PNG trong images", "Chỉ nội dung commit message"),
                "Workflow được khai báo trong tệp YAML dưới thư mục .github/workflows của repository.",
            ),
            Question(
                "Job và step",
                "Một job GitHub Actions chứa gì?",
                "Các step chạy trên cùng runner của job",
                ("Chỉ issue của repository", "Các branch không có quan hệ thực thi"),
                "Job gồm các step; step có thể chạy command hoặc dùng một action.",
            ),
            Question(
                "Sự kiện",
                "Workflow có thể được kích hoạt bằng sự kiện nào?",
                "push hoặc pull_request được cấu hình",
                ("Mọi lần mở màn hình máy tính theo mặc định", "Chỉ lúc repository bị xóa"),
                "Khóa on khai báo các sự kiện như push, pull_request hoặc workflow_dispatch.",
            ),
        ),
    ),
    Course(
        "Scrum và quản lý sản phẩm",
        "The Scrum Guide 2020",
        "https://scrumguides.org/scrum-guide.html",
        "Hiểu hoạt động nhóm phát triển phần mềm.",
        "Soạn Product Goal, sắp thứ tự backlog và đề xuất Sprint Goal có thể kiểm chứng.",
        (
            Question(
                "Product Backlog",
                "Ai chịu trách nhiệm giải trình về việc sắp thứ tự Product Backlog?",
                "Product Owner",
                ("Chỉ khách hàng bất kỳ", "Chỉ người tổ chức họp"),
                "Product Owner chịu trách nhiệm quản lý hiệu quả Product Backlog, trong đó có sắp thứ tự các mục.",
            ),
            Question(
                "Sprint",
                "Theo Scrum Guide 2020, Sprint có độ dài như thế nào?",
                "Cố định, một tháng hoặc ngắn hơn",
                ("Luôn đúng 90 ngày", "Không bao giờ có giới hạn thời gian"),
                "Sprint là sự kiện có thời lượng cố định không quá một tháng để tạo tính nhất quán.",
            ),
            Question(
                "Definition of Done",
                "Definition of Done mô tả điều gì?",
                "Trạng thái Increment đáp ứng các tiêu chuẩn chất lượng cần thiết",
                ("Danh sách người tham gia cuộc họp", "Chỉ deadline của dự án"),
                "Definition of Done tạo sự hiểu biết chung về điều kiện chất lượng mà Increment phải đạt.",
            ),
        ),
    ),
    Course(
        "Thiết kế trải nghiệm Web dễ tiếp cận",
        "W3C WAI: Designing for Web Accessibility",
        "https://www.w3.org/WAI/tips/designing/",
        "Biết sử dụng một ứng dụng Web.",
        "Rà soát form đăng ký: nhãn, tương phản, focus, thông báo lỗi và điều hướng bằng bàn phím.",
        (
            Question(
                "Thông tin và màu sắc",
                "Lỗi nhập liệu nên được truyền đạt thế nào?",
                "Dùng mô tả văn bản hoặc dấu hiệu khác bên cạnh màu",
                ("Chỉ đổi sang màu đỏ", "Ẩn trường nhập bị lỗi"),
                "Không nên dùng màu làm phương tiện duy nhất truyền tải thông tin quan trọng.",
            ),
            Question(
                "Focus",
                "Người điều hướng bằng bàn phím cần nhìn thấy gì?",
                "Chỉ báo focus của điều khiển hiện tại",
                ("Chỉ con trỏ chuột", "Không cần dấu hiệu điều hướng"),
                "Focus hiển thị giúp nhận biết điều khiển nào sẽ nhận thao tác bàn phím.",
            ),
            Question(
                "Nhãn form",
                "Một ô nhập dữ liệu nên có gì để người dùng hiểu mục đích?",
                "Nhãn hoặc hướng dẫn rõ ràng, liên kết phù hợp với ô nhập",
                ("Chỉ một màu nền khác", "Một ký hiệu ngẫu nhiên không giải thích"),
                "Nhãn và hướng dẫn rõ ràng giúp hiểu thông tin được yêu cầu và cách nhập.",
            ),
        ),
    ),
    Course(
        "Quản lý công việc và dự án phần mềm",
        "GitHub: About Projects",
        "https://docs.github.com/en/issues/planning-and-tracking-with-projects/learning-about-projects/about-projects",
        "Biết issue, pull request và công việc theo nhóm.",
        "Lập project có 10 issue, trường status và priority; liên kết PR và theo dõi công việc đang làm.",
        (
            Question(
                "Projects",
                "GitHub Projects có thể tổ chức các đối tượng nào?",
                "Issue, pull request và draft issue",
                ("Chỉ ảnh đại diện", "Chỉ mật khẩu tài khoản"),
                "Projects kết hợp issue, pull request và draft issue để lập kế hoạch và theo dõi công việc.",
            ),
            Question(
                "Các chế độ xem",
                "Dữ liệu project có thể được xem dưới dạng nào?",
                "Table, board hoặc roadmap phù hợp",
                ("Chỉ một video", "Chỉ màn hình terminal bắt buộc"),
                "Các view khác nhau trình bày cùng dữ liệu theo cách phù hợp với kế hoạch và quy trình.",
            ),
            Question(
                "Trường tùy chỉnh",
                "Custom field trong project giúp làm gì?",
                "Theo dõi thông tin như priority hoặc iteration",
                ("Tự động chứng minh công việc đã kiểm thử", "Thay thế nội dung mọi issue"),
                "Trường tùy chỉnh biểu diễn thuộc tính phục vụ tổ chức công việc; chúng không thay cho bằng chứng hoàn thành.",
            ),
        ),
    ),
    Course(
        "Tiếng Anh kỹ thuật",
        "Google developer documentation style guide",
        "https://developers.google.com/style/highlights",
        "Đọc được câu tiếng Anh đơn giản.",
        "Viết issue tiếng Anh gồm expected behavior, actual behavior và steps to reproduce; ưu tiên câu rõ ràng.",
        (
            Question(
                "Active voice",
                "Câu nào dùng active voice và nêu rõ người thực hiện?",
                "The server validates the token.",
                ("The token is validated.", "Validation is done."),
                "Active voice đặt chủ thể server trước động từ validates, giúp nêu rõ tác nhân.",
            ),
            Question(
                "Hướng dẫn trực tiếp",
                "Câu nào hướng dẫn thao tác trực tiếp và ngắn gọn?",
                "Click Save to store your changes.",
                (
                    "It might perhaps be possible to make a saving occur.",
                    "The occurrence of a save can happen.",
                ),
                "Câu mệnh lệnh ngắn chỉ rõ hành động và kết quả, giúp người đọc dễ làm theo.",
            ),
            Question(
                "Rõ ràng",
                "Khi viết tài liệu cho người đọc quốc tế, nên ưu tiên cách diễn đạt nào?",
                "Từ quen thuộc, câu rõ ràng và thuật ngữ nhất quán",
                ("Thành ngữ địa phương ở mọi câu", "Đổi tên cùng một khái niệm liên tục"),
                "Cách diễn đạt rõ và nhất quán giảm hiểu nhầm cho người đọc và công cụ dịch.",
            ),
        ),
    ),
    Course(
        "Bảo vệ dữ liệu và bí mật ứng dụng",
        "OWASP Cryptographic Storage Cheat Sheet",
        "https://cheatsheetseries.owasp.org/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html",
        "Hiểu tệp, database và tài khoản.",
        "Lập sơ đồ dữ liệu cần lưu; loại bỏ dữ liệu không cần thiết và mô tả quản lý khóa tách khỏi dữ liệu.",
        (
            Question(
                "Tối thiểu hóa dữ liệu",
                "Cách đầu tiên để giảm rủi ro dữ liệu nhạy cảm là gì?",
                "Không lưu dữ liệu nhạy cảm không cần thiết",
                ("Sao chép dữ liệu đến mọi môi trường", "Ghi toàn bộ vào log công khai"),
                "Giảm lượng dữ liệu nhạy cảm lưu trữ làm giảm phạm vi cần bảo vệ và hậu quả khi sự cố xảy ra.",
            ),
            Question(
                "Thuật toán",
                "Khi cần mã hóa dữ liệu ứng dụng, nên chọn cách nào?",
                "Thư viện và thuật toán đã được thẩm định phù hợp",
                ("Tự thiết kế thuật toán bí mật", "Đổi tên file thành .encrypted"),
                "Không tự chế thuật toán mật mã; dùng thư viện đáng tin và cấu hình phù hợp.",
            ),
            Question(
                "Quản lý khóa",
                "Khóa mã hóa nên được quản lý thế nào?",
                "Tách khỏi dữ liệu được mã hóa, với quyền truy cập hạn chế",
                ("Lưu công khai cùng bản dump", "Đặt nguyên văn trong repository công khai"),
                "Tách quản lý khóa khỏi dữ liệu giảm nguy cơ mất đồng thời cả dữ liệu và phương tiện giải mã.",
            ),
        ),
    ),
    Course(
        "Trực quan hóa dữ liệu",
        "Matplotlib: Plot types",
        "https://matplotlib.org/stable/plot_types/index.html",
        "Hiểu dữ liệu số và bảng đơn giản.",
        "Tạo line chart, bar chart và scatter plot; đặt nhãn trục, đơn vị và giải thích lựa chọn biểu đồ.",
        (
            Question(
                "Line chart",
                "Biểu đồ nào thường phù hợp để nối các quan sát theo thứ tự thời gian?",
                "Line chart",
                ("Một biểu tượng trang trí không có dữ liệu", "Chỉ văn bản tên biến"),
                "Line chart nối các điểm theo thứ tự, hỗ trợ quan sát sự thay đổi qua thời gian.",
            ),
            Question(
                "Bar chart",
                "Biểu đồ nào thường dùng để so sánh giá trị giữa các nhóm rời rạc?",
                "Bar chart",
                ("Chỉ ảnh nền", "Chỉ trục không có điểm"),
                "Các thanh biểu diễn giá trị của từng nhóm, thuận tiện cho so sánh định lượng.",
            ),
            Question(
                "Scatter plot",
                "Scatter plot thường biểu diễn điều gì?",
                "Các cặp giá trị của hai biến số",
                ("Chỉ quyền người dùng", "Một file âm thanh"),
                "Mỗi điểm biểu diễn một cặp (x, y), giúp quan sát quan hệ và phân bố giữa hai biến.",
            ),
        ),
    ),
)


def validate_content():
    assert len(COURSES) == 20
    assert len({course.title for course in COURSES}) == 20
    for course in COURSES:
        assert course.source_url.startswith("https://")
        assert len(course.questions) == 3
        for question in course.questions:
            assert len({question.correct, *question.wrong}) == 3
            assert question.prompt and question.explanation and question.topic
