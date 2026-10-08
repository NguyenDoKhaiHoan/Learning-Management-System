-- Canonical LMS schema. MySQL 8.0.16+; UTF-8.
-- Fresh empty lms database only. Existing databases: alembic upgrade head.
CREATE DATABASE IF NOT EXISTS lms CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE lms;
SET time_zone = '+00:00';

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 0001_p0

CREATE TABLE permissions (
    code VARCHAR(100) NOT NULL, 
    description VARCHAR(500), 
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
    CONSTRAINT pk_permissions PRIMARY KEY (id), 
    CONSTRAINT uq_permissions_code UNIQUE (code)
)CHARSET=utf8mb4 ENGINE=InnoDB COLLATE utf8mb4_unicode_ci;

CREATE TABLE roles (
    code VARCHAR(32) NOT NULL, 
    name VARCHAR(100) NOT NULL, 
    description VARCHAR(500), 
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
    CONSTRAINT pk_roles PRIMARY KEY (id), 
    CONSTRAINT uq_roles_code UNIQUE (code)
)CHARSET=utf8mb4 ENGINE=InnoDB COLLATE utf8mb4_unicode_ci;

CREATE TABLE users (
    email VARCHAR(254) NOT NULL, 
    username VARCHAR(64) NOT NULL, 
    hashed_password VARCHAR(255) NOT NULL, 
    status ENUM('ACTIVE','INACTIVE','LOCKED') NOT NULL DEFAULT 'INACTIVE', 
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
    deleted_at DATETIME(6), 
    CONSTRAINT pk_users PRIMARY KEY (id), 
    CONSTRAINT uq_users_email UNIQUE (email), 
    CONSTRAINT uq_users_username UNIQUE (username)
)CHARSET=utf8mb4 ENGINE=InnoDB COLLATE utf8mb4_unicode_ci;

CREATE INDEX ix_users_deleted_at ON users (deleted_at);

CREATE INDEX ix_users_status ON users (status);

CREATE TABLE audit_logs (
    actor_id BIGINT UNSIGNED, 
    action VARCHAR(100) NOT NULL, 
    resource VARCHAR(100) NOT NULL, 
    resource_id VARCHAR(64), 
    timestamp DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
    ip_address VARCHAR(45), 
    trace_id VARCHAR(64) NOT NULL, 
    details JSON, 
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
    CONSTRAINT pk_audit_logs PRIMARY KEY (id), 
    CONSTRAINT fk_audit_logs_actor_id_users FOREIGN KEY(actor_id) REFERENCES users (id) ON DELETE RESTRICT
)CHARSET=utf8mb4 ENGINE=InnoDB COLLATE utf8mb4_unicode_ci;

CREATE INDEX ix_audit_logs_actor_timestamp ON audit_logs (actor_id, timestamp);

CREATE INDEX ix_audit_logs_resource_id ON audit_logs (resource, resource_id);

CREATE INDEX ix_audit_logs_timestamp ON audit_logs (timestamp);

CREATE INDEX ix_audit_logs_trace_id ON audit_logs (trace_id);

CREATE TABLE courses (
    code VARCHAR(64) NOT NULL, 
    title VARCHAR(255) NOT NULL, 
    description TEXT, 
    status ENUM('DRAFT','PUBLISHED','ARCHIVED') NOT NULL DEFAULT 'DRAFT', 
    created_by BIGINT UNSIGNED NOT NULL, 
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
    deleted_at DATETIME(6), 
    CONSTRAINT pk_courses PRIMARY KEY (id), 
    CONSTRAINT fk_courses_created_by_users FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE RESTRICT, 
    CONSTRAINT uq_courses_code UNIQUE (code)
)CHARSET=utf8mb4 ENGINE=InnoDB COLLATE utf8mb4_unicode_ci;

CREATE INDEX ix_courses_created_by ON courses (created_by);

CREATE INDEX ix_courses_deleted_at ON courses (deleted_at);

CREATE INDEX ix_courses_status ON courses (status);

CREATE TABLE refresh_tokens (
    user_id BIGINT UNSIGNED NOT NULL, 
    token_hash CHAR(64) COLLATE ascii_bin NOT NULL, 
    family_id CHAR(36) COLLATE ascii_bin NOT NULL, 
    expires_at DATETIME(6) NOT NULL, 
    revoked_at DATETIME(6), 
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
    CONSTRAINT pk_refresh_tokens PRIMARY KEY (id), 
    CONSTRAINT ck_refresh_tokens_expiry_after_creation CHECK (expires_at > created_at), 
    CONSTRAINT fk_refresh_tokens_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE RESTRICT, 
    CONSTRAINT uq_refresh_tokens_token_hash UNIQUE (token_hash)
)CHARSET=utf8mb4 ENGINE=InnoDB COLLATE utf8mb4_unicode_ci;

CREATE INDEX ix_refresh_tokens_expires_at ON refresh_tokens (expires_at);

CREATE INDEX ix_refresh_tokens_family_id ON refresh_tokens (family_id);

CREATE INDEX ix_refresh_tokens_user_revoked ON refresh_tokens (user_id, revoked_at);

CREATE TABLE role_permissions (
    role_id BIGINT UNSIGNED NOT NULL, 
    permission_id BIGINT UNSIGNED NOT NULL, 
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
    CONSTRAINT pk_role_permissions PRIMARY KEY (id), 
    CONSTRAINT fk_role_permissions_permission_id_permissions FOREIGN KEY(permission_id) REFERENCES permissions (id) ON DELETE RESTRICT, 
    CONSTRAINT fk_role_permissions_role_id_roles FOREIGN KEY(role_id) REFERENCES roles (id) ON DELETE RESTRICT, 
    CONSTRAINT uq_role_permissions_role_id UNIQUE (role_id, permission_id)
)CHARSET=utf8mb4 ENGINE=InnoDB COLLATE utf8mb4_unicode_ci;

CREATE INDEX ix_role_permissions_permission_id ON role_permissions (permission_id);

CREATE TABLE security_events (
    actor_id BIGINT UNSIGNED, 
    event_type ENUM('LOGIN_SUCCEEDED','LOGIN_FAILED','TOKEN_REVOKED','TOKEN_REUSE_DETECTED','ACCESS_DENIED','PASSWORD_CHANGED','ACCOUNT_LOCKED') NOT NULL, 
    severity ENUM('INFO','WARNING','CRITICAL') NOT NULL DEFAULT 'INFO', 
    ip_address VARCHAR(45), 
    trace_id VARCHAR(64) NOT NULL, 
    details JSON, 
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
    CONSTRAINT pk_security_events PRIMARY KEY (id), 
    CONSTRAINT fk_security_events_actor_id_users FOREIGN KEY(actor_id) REFERENCES users (id) ON DELETE RESTRICT
)CHARSET=utf8mb4 ENGINE=InnoDB COLLATE utf8mb4_unicode_ci;

CREATE INDEX ix_security_events_actor_created ON security_events (actor_id, created_at);

CREATE INDEX ix_security_events_event_type ON security_events (event_type);

CREATE INDEX ix_security_events_severity ON security_events (severity);

CREATE INDEX ix_security_events_trace_id ON security_events (trace_id);

CREATE TABLE user_roles (
    user_id BIGINT UNSIGNED NOT NULL, 
    role_id BIGINT UNSIGNED NOT NULL, 
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
    CONSTRAINT pk_user_roles PRIMARY KEY (id), 
    CONSTRAINT fk_user_roles_role_id_roles FOREIGN KEY(role_id) REFERENCES roles (id) ON DELETE RESTRICT, 
    CONSTRAINT fk_user_roles_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE RESTRICT, 
    CONSTRAINT uq_user_roles_user_id UNIQUE (user_id, role_id)
)CHARSET=utf8mb4 ENGINE=InnoDB COLLATE utf8mb4_unicode_ci;

CREATE INDEX ix_user_roles_role_id ON user_roles (role_id);

CREATE TABLE course_staff (
    course_id BIGINT UNSIGNED NOT NULL, 
    user_id BIGINT UNSIGNED NOT NULL, 
    `role` ENUM('INSTRUCTOR','ASSISTANT') NOT NULL, 
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
    CONSTRAINT pk_course_staff PRIMARY KEY (id), 
    CONSTRAINT fk_course_staff_course_id_courses FOREIGN KEY(course_id) REFERENCES courses (id) ON DELETE RESTRICT, 
    CONSTRAINT fk_course_staff_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE RESTRICT, 
    CONSTRAINT uq_course_staff_course_id UNIQUE (course_id, user_id)
)CHARSET=utf8mb4 ENGINE=InnoDB COLLATE utf8mb4_unicode_ci;

CREATE INDEX ix_course_staff_user_id ON course_staff (user_id);

CREATE TABLE enrollments (
    student_id BIGINT UNSIGNED NOT NULL, 
    course_id BIGINT UNSIGNED NOT NULL, 
    status ENUM('PENDING','ACTIVE','SUSPENDED','COMPLETED') NOT NULL DEFAULT 'PENDING', 
    completed_at DATETIME(6), 
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
    CONSTRAINT pk_enrollments PRIMARY KEY (id), 
    CONSTRAINT ck_enrollments_completion_consistent CHECK ((status = 'COMPLETED' AND completed_at IS NOT NULL) OR (status <> 'COMPLETED' AND completed_at IS NULL)), 
    CONSTRAINT fk_enrollments_course_id_courses FOREIGN KEY(course_id) REFERENCES courses (id) ON DELETE RESTRICT, 
    CONSTRAINT fk_enrollments_student_id_users FOREIGN KEY(student_id) REFERENCES users (id) ON DELETE RESTRICT, 
    CONSTRAINT uq_enrollments_student_id UNIQUE (student_id, course_id)
)CHARSET=utf8mb4 ENGINE=InnoDB COLLATE utf8mb4_unicode_ci;

CREATE INDEX ix_enrollments_course_status ON enrollments (course_id, status);

CREATE INDEX ix_enrollments_status ON enrollments (status);

CREATE TABLE modules (
    course_id BIGINT UNSIGNED NOT NULL, 
    title VARCHAR(255) NOT NULL, 
    position INTEGER UNSIGNED NOT NULL, 
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
    deleted_at DATETIME(6), 
    CONSTRAINT pk_modules PRIMARY KEY (id), 
    CONSTRAINT ck_modules_positive_position CHECK (position > 0), 
    CONSTRAINT fk_modules_course_id_courses FOREIGN KEY(course_id) REFERENCES courses (id) ON DELETE RESTRICT, 
    CONSTRAINT uq_modules_course_id UNIQUE (course_id, position)
)CHARSET=utf8mb4 ENGINE=InnoDB COLLATE utf8mb4_unicode_ci;

CREATE INDEX ix_modules_deleted_at ON modules (deleted_at);

CREATE TABLE lessons (
    module_id BIGINT UNSIGNED NOT NULL, 
    title VARCHAR(255) NOT NULL, 
    position INTEGER UNSIGNED NOT NULL, 
    lesson_type ENUM('VIDEO','ARTICLE','DOCUMENT','LIVE') NOT NULL, 
    is_preview BOOL NOT NULL DEFAULT '0', 
    content TEXT, 
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
    deleted_at DATETIME(6), 
    CONSTRAINT pk_lessons PRIMARY KEY (id), 
    CONSTRAINT ck_lessons_boolean_preview CHECK (is_preview IN (0, 1)), 
    CONSTRAINT ck_lessons_positive_position CHECK (position > 0), 
    CONSTRAINT fk_lessons_module_id_modules FOREIGN KEY(module_id) REFERENCES modules (id) ON DELETE RESTRICT, 
    CONSTRAINT uq_lessons_module_id UNIQUE (module_id, position)
)CHARSET=utf8mb4 ENGINE=InnoDB COLLATE utf8mb4_unicode_ci;

CREATE INDEX ix_lessons_deleted_at ON lessons (deleted_at);

CREATE TABLE lesson_resources (
    lesson_id BIGINT UNSIGNED NOT NULL, 
    title VARCHAR(255) NOT NULL, 
    resource_type ENUM('FILE','LINK') NOT NULL, 
    location VARCHAR(2048) NOT NULL, 
    mime_type VARCHAR(127), 
    size_bytes BIGINT UNSIGNED, 
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
    deleted_at DATETIME(6), 
    CONSTRAINT pk_lesson_resources PRIMARY KEY (id), 
    CONSTRAINT fk_lesson_resources_lesson_id_lessons FOREIGN KEY(lesson_id) REFERENCES lessons (id) ON DELETE RESTRICT
)CHARSET=utf8mb4 ENGINE=InnoDB COLLATE utf8mb4_unicode_ci;

CREATE INDEX ix_lesson_resources_deleted_at ON lesson_resources (deleted_at);

CREATE INDEX ix_lesson_resources_lesson_id ON lesson_resources (lesson_id);

INSERT INTO alembic_version (version_num) VALUES ('0001_p0');

-- Running upgrade 0001_p0 -> 0002_week3_learning

ALTER TABLE lesson_resources ADD COLUMN sha256 VARCHAR(64);

ALTER TABLE lesson_resources ADD COLUMN uploaded_by BIGINT UNSIGNED;

ALTER TABLE lesson_resources ADD CONSTRAINT fk_lesson_resources_uploaded_by_users FOREIGN KEY(uploaded_by) REFERENCES users (id) ON DELETE RESTRICT;

CREATE TABLE completion_rules (
    course_id BIGINT UNSIGNED NOT NULL, 
    required_lesson_percent NUMERIC(5, 2) NOT NULL DEFAULT 100.00, 
    updated_by BIGINT UNSIGNED NOT NULL, 
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
    CONSTRAINT pk_completion_rules PRIMARY KEY (id), 
    CONSTRAINT ck_completion_rules_percent CHECK (required_lesson_percent > 0 AND required_lesson_percent <= 100), 
    CONSTRAINT fk_completion_rules_course_id_courses FOREIGN KEY(course_id) REFERENCES courses (id), 
    CONSTRAINT fk_completion_rules_updated_by_users FOREIGN KEY(updated_by) REFERENCES users (id), 
    CONSTRAINT uq_completion_rules_course_id UNIQUE (course_id)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE TABLE lesson_progress (
    enrollment_id BIGINT UNSIGNED NOT NULL, 
    lesson_id BIGINT UNSIGNED NOT NULL, 
    status ENUM('NOT_STARTED','IN_PROGRESS','COMPLETED') NOT NULL DEFAULT 'NOT_STARTED', 
    last_position_seconds INTEGER UNSIGNED NOT NULL DEFAULT '0', 
    started_at DATETIME(6), 
    completed_at DATETIME(6), 
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
    CONSTRAINT pk_lesson_progress PRIMARY KEY (id), 
    CONSTRAINT ck_lesson_progress_status_times CHECK ((status = 'NOT_STARTED' AND started_at IS NULL AND completed_at IS NULL) OR (status = 'IN_PROGRESS' AND started_at IS NOT NULL AND completed_at IS NULL) OR (status = 'COMPLETED' AND started_at IS NOT NULL AND completed_at IS NOT NULL)), 
    CONSTRAINT fk_lesson_progress_enrollment_id_enrollments FOREIGN KEY(enrollment_id) REFERENCES enrollments (id), 
    CONSTRAINT fk_lesson_progress_lesson_id_lessons FOREIGN KEY(lesson_id) REFERENCES lessons (id), 
    CONSTRAINT uq_lesson_progress_enrollment_lesson UNIQUE (enrollment_id, lesson_id)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE INDEX ix_lesson_progress_lesson_id ON lesson_progress (lesson_id);

CREATE TABLE course_progress (
    enrollment_id BIGINT UNSIGNED NOT NULL, 
    completed_lessons INTEGER UNSIGNED NOT NULL DEFAULT '0', 
    total_lessons INTEGER UNSIGNED NOT NULL DEFAULT '0', 
    progress_percent NUMERIC(5, 2) NOT NULL DEFAULT '0.00', 
    completed_at DATETIME(6), 
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
    CONSTRAINT pk_course_progress PRIMARY KEY (id), 
    CONSTRAINT ck_course_progress_values CHECK (completed_lessons <= total_lessons AND progress_percent >= 0 AND progress_percent <= 100), 
    CONSTRAINT fk_course_progress_enrollment_id_enrollments FOREIGN KEY(enrollment_id) REFERENCES enrollments (id), 
    CONSTRAINT uq_course_progress_enrollment_id UNIQUE (enrollment_id)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_unicode_ci;

UPDATE alembic_version SET version_num='0002_week3_learning' WHERE alembic_version.version_num = '0001_p0';

-- Running upgrade 0002_week3_learning -> 0003_week3_assignments

ALTER TABLE completion_rules ADD COLUMN require_submitted_assignments BOOL NOT NULL DEFAULT 0;

ALTER TABLE course_progress ADD COLUMN completed_assignments INTEGER UNSIGNED NOT NULL DEFAULT '0';

ALTER TABLE course_progress ADD COLUMN total_assignments INTEGER UNSIGNED NOT NULL DEFAULT '0';

CREATE TABLE assignments (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
    course_id BIGINT UNSIGNED NOT NULL, 
    title VARCHAR(255) NOT NULL, 
    description TEXT NOT NULL, 
    status ENUM('DRAFT','PUBLISHED','CLOSED','ARCHIVED') NOT NULL DEFAULT 'DRAFT', 
    opens_at DATETIME(6) NOT NULL, 
    due_at DATETIME(6) NOT NULL, 
    allow_late BOOL NOT NULL DEFAULT 0, 
    late_until DATETIME(6), 
    max_attempts INTEGER UNSIGNED NOT NULL, 
    max_file_bytes BIGINT UNSIGNED NOT NULL, 
    allowed_mime_types VARCHAR(500) NOT NULL, 
    max_score NUMERIC(8, 2) NOT NULL, 
    created_by BIGINT UNSIGNED NOT NULL, 
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
    deleted_at DATETIME(6), 
    PRIMARY KEY (id), 
    CONSTRAINT ck_assignments_window CHECK (opens_at < due_at), 
    CONSTRAINT ck_assignments_late_policy CHECK ((allow_late=0 AND late_until IS NULL) OR (allow_late=1 AND late_until > due_at)), 
    CONSTRAINT ck_assignments_limits CHECK (max_attempts > 0 AND max_file_bytes > 0 AND max_score > 0), 
    CONSTRAINT fk_assignments_course_id_courses FOREIGN KEY(course_id) REFERENCES courses (id), 
    CONSTRAINT fk_assignments_created_by_users FOREIGN KEY(created_by) REFERENCES users (id)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE INDEX ix_assignments_course_id ON assignments (course_id, status);

UPDATE alembic_version SET version_num='0003_week3_assignments' WHERE alembic_version.version_num = '0002_week3_learning';

-- Running upgrade 0003_week3_assignments -> 0004_week3_submissions

CREATE TABLE assignment_submissions (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
    assignment_id BIGINT UNSIGNED NOT NULL, 
    enrollment_id BIGINT UNSIGNED NOT NULL, 
    version INTEGER UNSIGNED NOT NULL, 
    status ENUM('SUBMITTED','LATE') NOT NULL, 
    answer_text TEXT, 
    submitted_at DATETIME(6) NOT NULL, 
    submitted_by BIGINT UNSIGNED NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_assignment_submissions_version CHECK (version > 0), 
    CONSTRAINT fk_assignment_submissions_assignment_id_assignments FOREIGN KEY(assignment_id) REFERENCES assignments (id), 
    CONSTRAINT fk_assignment_submissions_enrollment_id_enrollments FOREIGN KEY(enrollment_id) REFERENCES enrollments (id), 
    CONSTRAINT fk_assignment_submissions_submitted_by_users FOREIGN KEY(submitted_by) REFERENCES users (id), 
    CONSTRAINT uq_assignment_submissions_version UNIQUE (assignment_id, enrollment_id, version)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE INDEX ix_assignment_submissions_enrollment_id ON assignment_submissions (enrollment_id);

CREATE TABLE submission_files (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
    submission_id BIGINT UNSIGNED NOT NULL, 
    title VARCHAR(255) NOT NULL, 
    location VARCHAR(512) NOT NULL, 
    mime_type VARCHAR(127) NOT NULL, 
    size_bytes BIGINT UNSIGNED NOT NULL, 
    sha256 VARCHAR(64) NOT NULL, 
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
    PRIMARY KEY (id), 
    CONSTRAINT ck_submission_files_positive_size CHECK (size_bytes > 0), 
    CONSTRAINT fk_submission_files_submission_id_assignment_submissions FOREIGN KEY(submission_id) REFERENCES assignment_submissions (id)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE INDEX ix_submission_files_submission_id ON submission_files (submission_id);

UPDATE alembic_version SET version_num='0004_week3_submissions' WHERE alembic_version.version_num = '0003_week3_assignments';

-- Running upgrade 0004_week3_submissions -> 0005_week4_exam_gradebook

CREATE TABLE question_banks (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
    course_id BIGINT UNSIGNED NOT NULL, 
    name VARCHAR(255) NOT NULL, 
    description TEXT, 
    status ENUM('DRAFT','PUBLISHED','ARCHIVED') NOT NULL DEFAULT 'DRAFT', 
    created_by BIGINT UNSIGNED NOT NULL, 
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
    PRIMARY KEY (id), 
    FOREIGN KEY(course_id) REFERENCES courses (id) ON DELETE RESTRICT, 
    FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE RESTRICT
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE INDEX ix_question_banks_course_status ON question_banks (course_id, status);

CREATE TABLE questions (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
    bank_id BIGINT UNSIGNED NOT NULL, 
    question_type ENUM('SINGLE','MULTIPLE','TRUE_FALSE') NOT NULL, 
    prompt TEXT NOT NULL, 
    explanation TEXT, 
    points NUMERIC(8, 2) NOT NULL DEFAULT '1.00', 
    status ENUM('DRAFT','PUBLISHED','ARCHIVED') NOT NULL DEFAULT 'DRAFT', 
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
    PRIMARY KEY (id), 
    CONSTRAINT ck_questions_positive_points CHECK (points > 0), 
    FOREIGN KEY(bank_id) REFERENCES question_banks (id) ON DELETE RESTRICT
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE INDEX ix_questions_bank_status ON questions (bank_id, status);

CREATE TABLE question_options (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
    question_id BIGINT UNSIGNED NOT NULL, 
    option_key VARCHAR(16) NOT NULL, 
    option_text TEXT NOT NULL, 
    is_correct BOOL NOT NULL DEFAULT 0, 
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
    PRIMARY KEY (id), 
    CONSTRAINT uq_question_options_key UNIQUE (question_id, option_key), 
    FOREIGN KEY(question_id) REFERENCES questions (id) ON DELETE RESTRICT
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE TABLE exams (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
    course_id BIGINT UNSIGNED NOT NULL, 
    title VARCHAR(255) NOT NULL, 
    instructions TEXT, 
    status ENUM('DRAFT','PUBLISHED','CLOSED','ARCHIVED') NOT NULL DEFAULT 'DRAFT', 
    opens_at DATETIME(6) NOT NULL, 
    due_at DATETIME(6) NOT NULL, 
    duration_seconds INTEGER UNSIGNED NOT NULL, 
    max_attempts INTEGER UNSIGNED NOT NULL DEFAULT '1', 
    shuffle_questions BOOL NOT NULL DEFAULT 0, 
    show_results BOOL NOT NULL DEFAULT 0, 
    pass_score NUMERIC(8, 2) NOT NULL DEFAULT '0.00', 
    created_by BIGINT UNSIGNED NOT NULL, 
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
    PRIMARY KEY (id), 
    CONSTRAINT ck_exams_window CHECK (opens_at < due_at), 
    CONSTRAINT ck_exams_limits CHECK (duration_seconds > 0 AND max_attempts > 0), 
    CONSTRAINT ck_exams_pass_score CHECK (pass_score >= 0), 
    FOREIGN KEY(course_id) REFERENCES courses (id) ON DELETE RESTRICT, 
    FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE RESTRICT
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE INDEX ix_exams_course_status ON exams (course_id, status);

CREATE TABLE exam_blueprints (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
    exam_id BIGINT UNSIGNED NOT NULL, 
    question_type ENUM('SINGLE','MULTIPLE','TRUE_FALSE') NOT NULL, 
    question_count INTEGER UNSIGNED NOT NULL, 
    points_each NUMERIC(8, 2) NOT NULL, 
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
    PRIMARY KEY (id), 
    CONSTRAINT ck_exam_blueprints_values CHECK (question_count > 0 AND points_each > 0), 
    CONSTRAINT uq_exam_blueprints_type UNIQUE (exam_id, question_type), 
    FOREIGN KEY(exam_id) REFERENCES exams (id) ON DELETE CASCADE
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE TABLE exam_questions (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
    exam_id BIGINT UNSIGNED NOT NULL, 
    question_id BIGINT UNSIGNED NOT NULL, 
    position INTEGER UNSIGNED NOT NULL, 
    points NUMERIC(8, 2) NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_exam_questions_question UNIQUE (exam_id, question_id), 
    CONSTRAINT uq_exam_questions_position UNIQUE (exam_id, position), 
    CONSTRAINT ck_exam_questions_values CHECK (position > 0 AND points > 0), 
    FOREIGN KEY(exam_id) REFERENCES exams (id) ON DELETE CASCADE, 
    FOREIGN KEY(question_id) REFERENCES questions (id) ON DELETE RESTRICT
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE TABLE exam_attempts (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
    exam_id BIGINT UNSIGNED NOT NULL, 
    enrollment_id BIGINT UNSIGNED NOT NULL, 
    attempt_no INTEGER UNSIGNED NOT NULL, 
    status ENUM('IN_PROGRESS','SUBMITTED','AUTO_SUBMITTED','CANCELLED') NOT NULL DEFAULT 'IN_PROGRESS', 
    started_at DATETIME(6) NOT NULL, 
    expires_at DATETIME(6) NOT NULL, 
    submitted_at DATETIME(6), 
    score NUMERIC(8, 2), 
    max_score NUMERIC(8, 2) NOT NULL, 
    server_version INTEGER UNSIGNED NOT NULL DEFAULT '0', 
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
    PRIMARY KEY (id), 
    CONSTRAINT ck_exam_attempts_window CHECK (attempt_no > 0 AND expires_at > started_at), 
    CONSTRAINT ck_exam_attempts_score CHECK (score IS NULL OR (score >= 0 AND score <= max_score)), 
    CONSTRAINT uq_exam_attempts_number UNIQUE (exam_id, enrollment_id, attempt_no), 
    FOREIGN KEY(exam_id) REFERENCES exams (id) ON DELETE RESTRICT, 
    FOREIGN KEY(enrollment_id) REFERENCES enrollments (id) ON DELETE RESTRICT
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE INDEX ix_exam_attempts_student_status ON exam_attempts (enrollment_id, status);

CREATE TABLE exam_answers (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
    attempt_id BIGINT UNSIGNED NOT NULL, 
    question_id BIGINT UNSIGNED NOT NULL, 
    selected_option_ids JSON, 
    answer_text TEXT, 
    is_correct BOOL, 
    points_awarded NUMERIC(8, 2), 
    answered_at DATETIME(6), 
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
    PRIMARY KEY (id), 
    CONSTRAINT uq_exam_answers_question UNIQUE (attempt_id, question_id), 
    FOREIGN KEY(attempt_id) REFERENCES exam_attempts (id) ON DELETE CASCADE, 
    FOREIGN KEY(question_id) REFERENCES questions (id) ON DELETE RESTRICT
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE TABLE gradebook_entries (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
    enrollment_id BIGINT UNSIGNED NOT NULL, 
    assessment_type ENUM('ASSIGNMENT','EXAM') NOT NULL, 
    assessment_id BIGINT UNSIGNED NOT NULL, 
    score NUMERIC(8, 2), 
    max_score NUMERIC(8, 2) NOT NULL, 
    status ENUM('DRAFT','PUBLISHED') NOT NULL DEFAULT 'DRAFT', 
    graded_by BIGINT UNSIGNED, 
    published_at DATETIME(6), 
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
    PRIMARY KEY (id), 
    CONSTRAINT ck_gradebook_scores CHECK (max_score > 0 AND (score IS NULL OR (score >= 0 AND score <= max_score))), 
    CONSTRAINT uq_gradebook_assessment UNIQUE (enrollment_id, assessment_type, assessment_id), 
    FOREIGN KEY(enrollment_id) REFERENCES enrollments (id) ON DELETE RESTRICT, 
    FOREIGN KEY(graded_by) REFERENCES users (id) ON DELETE RESTRICT
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE INDEX ix_gradebook_entries_enrollment_status ON gradebook_entries (enrollment_id, status);

UPDATE alembic_version SET version_num='0005_week4_exam_gradebook' WHERE alembic_version.version_num = '0004_week3_submissions';

-- Running upgrade 0005_week4_exam_gradebook -> 0006_exam_policy

CREATE TABLE question_categories (
        id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
        bank_id BIGINT UNSIGNED NOT NULL,
        name VARCHAR(255) NOT NULL,
        UNIQUE KEY uq_category_bank_name(bank_id, name),
        FOREIGN KEY (bank_id) REFERENCES question_banks(id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

ALTER TABLE questions
        ADD category_id BIGINT UNSIGNED NULL,
        ADD difficulty ENUM('EASY','MEDIUM','HARD') NOT NULL DEFAULT 'MEDIUM',
        ADD CONSTRAINT fk_questions_category FOREIGN KEY(category_id)
        REFERENCES question_categories(id);

ALTER TABLE exams ADD allow_resume BOOLEAN NOT NULL DEFAULT TRUE;

ALTER TABLE exam_blueprints
        ADD bank_id BIGINT UNSIGNED NULL,
        ADD category_id BIGINT UNSIGNED NULL,
        ADD difficulty ENUM('EASY','MEDIUM','HARD') NULL,
        ADD CONSTRAINT fk_blueprint_bank FOREIGN KEY(bank_id) REFERENCES question_banks(id),
        ADD CONSTRAINT fk_blueprint_category FOREIGN KEY(category_id)
        REFERENCES question_categories(id);

ALTER TABLE exam_attempts ADD question_snapshot JSON NULL;

UPDATE alembic_version SET version_num='0006_exam_policy' WHERE alembic_version.version_num = '0005_week4_exam_gradebook';

-- Running upgrade 0006_exam_policy -> 0007_grading

ALTER TABLE exam_attempts ADD graded_at DATETIME(6) NULL;

ALTER TABLE gradebook_entries
        ADD feedback TEXT NULL,
        ADD version INT UNSIGNED NOT NULL DEFAULT 1,
        ADD source_attempt_id BIGINT UNSIGNED NULL,
        ADD source_submission_id BIGINT UNSIGNED NULL,
        ADD CONSTRAINT fk_grade_attempt FOREIGN KEY(source_attempt_id) REFERENCES exam_attempts(id),
        ADD CONSTRAINT fk_grade_submission FOREIGN KEY(source_submission_id)
            REFERENCES assignment_submissions(id);

CREATE TABLE grade_items (
        id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
        grade_id BIGINT UNSIGNED NOT NULL,
        item_key VARCHAR(64) NOT NULL,
        label TEXT NOT NULL,
        score DECIMAL(8,2) NOT NULL,
        max_score DECIMAL(8,2) NOT NULL,
        feedback TEXT NULL,
        UNIQUE KEY uq_grade_item(grade_id,item_key),
        CONSTRAINT ck_grade_item_score CHECK(max_score>0 AND score>=0 AND score<=max_score),
        FOREIGN KEY(grade_id) REFERENCES gradebook_entries(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE grade_history (
        id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
        grade_id BIGINT UNSIGNED NOT NULL,
        version INT UNSIGNED NOT NULL,
        action ENUM('AUTO_GRADE','DRAFT','PUBLISH','REVISE') NOT NULL,
        actor_id BIGINT UNSIGNED NULL,
        reason TEXT NULL,
        snapshot JSON NOT NULL,
        created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
        UNIQUE KEY uq_grade_history_version(grade_id,version),
        FOREIGN KEY(grade_id) REFERENCES gradebook_entries(id),
        FOREIGN KEY(actor_id) REFERENCES users(id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_attempt_expiry ON exam_attempts(status,expires_at);

UPDATE alembic_version SET version_num='0007_grading' WHERE alembic_version.version_num = '0006_exam_policy';

-- Running upgrade 0007_grading -> 0008_assessment_completion

ALTER TABLE completion_rules
        ADD require_published_assignment_grades BOOLEAN NOT NULL DEFAULT FALSE,
        ADD require_published_exam_grades BOOLEAN NOT NULL DEFAULT FALSE,
        ADD minimum_grade_percent DECIMAL(5,2) NOT NULL DEFAULT 50.00,
        ADD CONSTRAINT ck_completion_grade_percent CHECK
            (minimum_grade_percent >= 0 AND minimum_grade_percent <= 100);

ALTER TABLE course_progress
        ADD passed_assignments INT UNSIGNED NOT NULL DEFAULT 0,
        ADD total_exams INT UNSIGNED NOT NULL DEFAULT 0,
        ADD passed_exams INT UNSIGNED NOT NULL DEFAULT 0;

UPDATE alembic_version SET version_num='0008_assessment_completion' WHERE alembic_version.version_num = '0007_grading';


-- Running upgrade 0008_assessment_completion -> 0009_notifications

CREATE TABLE notifications (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    recipient_id BIGINT UNSIGNED NOT NULL,
    course_id BIGINT UNSIGNED NULL,
    type VARCHAR(64) NOT NULL,
    title VARCHAR(255) NOT NULL,
    body TEXT NOT NULL,
    resource_type VARCHAR(64) NULL,
    resource_id BIGINT UNSIGNED NULL,
    is_read BOOLEAN NOT NULL DEFAULT FALSE,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    read_at DATETIME(6) NULL,
    PRIMARY KEY (id),
    CONSTRAINT fk_notifications_recipient FOREIGN KEY (recipient_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_notifications_course FOREIGN KEY (course_id) REFERENCES courses(id),
    INDEX ix_notifications_recipient_created (recipient_id, created_at),
    INDEX ix_notifications_recipient_unread (recipient_id, is_read, created_at)
)CHARSET=utf8mb4 ENGINE=InnoDB COLLATE utf8mb4_unicode_ci;

UPDATE alembic_version SET version_num='0009_notifications' WHERE version_num='0008_assessment_completion';
