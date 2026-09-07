-- Generated from Alembic 0001_p0. MySQL 8.0.16+; review only.
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

