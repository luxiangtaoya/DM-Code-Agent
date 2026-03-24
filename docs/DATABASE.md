# AI自动化测试平台 数据库设计文档

## 数据库选型
- **类型**: SQLite
- **文件位置**: `backend/data/testing_platform.db`

---

## 数据表设计

### 1. 项目表 (projects)

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | 项目ID |
| name | TEXT | NOT NULL | 项目名称 |
| description | TEXT | | 项目描述 |
| status | TEXT | NOT NULL DEFAULT 'active' | 状态: active/archived |
| created_at | DATETIME | NOT NULL DEFAULT CURRENT_TIMESTAMP | 创建时间 |
| updated_at | DATETIME | NOT NULL DEFAULT CURRENT_TIMESTAMP | 更新时间 |

**索引:**
- `idx_projects_name`: name
- `idx_projects_status`: status

---

### 2. 需求文档表 (documents)

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | 文档ID |
| project_id | INTEGER | NOT NULL, FOREIGN KEY -> projects(id) | 所属项目 |
| title | TEXT | NOT NULL | 文档标题 |
| file_path | TEXT | NOT NULL | 文件存储路径 |
| file_type | TEXT | NOT NULL | 文件类型: pdf/docx |
| file_size | INTEGER | | 文件大小(字节) |
| extracted_text | TEXT | | 提取的文本内容 |
| created_at | DATETIME | NOT NULL DEFAULT CURRENT_TIMESTAMP | 创建时间 |

**索引:**
- `idx_documents_project_id`: project_id
- `idx_documents_created_at`: created_at

---

### 3. 测试用例表 (test_cases)

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | 用例ID |
| project_id | INTEGER | NOT NULL, FOREIGN KEY -> projects(id) | 所属项目 |
| document_id | INTEGER | FOREIGN KEY -> documents(id) | 来源文档 |
| name | TEXT | NOT NULL | 用例名称 |
| description | TEXT | | 用例描述 |
| precondition | TEXT | | 前置条件 |
| steps | TEXT | NOT NULL | 测试步骤(JSON数组) |
| expected_result | TEXT | NOT NULL | 预期结果 |
| priority | TEXT | NOT NULL DEFAULT 'medium' | 优先级: high/medium/low |
| tags | TEXT | | 标签(JSON数组) |
| status | TEXT | NOT NULL DEFAULT 'active' | 状态: active/archived |
| created_at | DATETIME | NOT NULL DEFAULT CURRENT_TIMESTAMP | 创建时间 |
| updated_at | DATETIME | NOT NULL DEFAULT CURRENT_TIMESTAMP | 更新时间 |

**索引:**
- `idx_test_cases_project_id`: project_id
- `idx_test_cases_priority`: priority
- `idx_test_cases_status`: status

---

### 4. 测试执行表 (test_executions)

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | TEXT | PRIMARY KEY | 执行ID(UUID) |
| project_id | INTEGER | NOT NULL, FOREIGN KEY -> projects(id) | 所属项目 |
| testcase_id | INTEGER | NOT NULL, FOREIGN KEY -> test_cases(id) | 测试用例ID |
| status | TEXT | NOT NULL DEFAULT 'pending' | 状态: pending/running/completed/failed/stopped |
| start_time | DATETIME | | 开始时间 |
| end_time | DATETIME | | 结束时间 |
| duration | INTEGER | | 执行时长(秒) |
| result | TEXT | | 结果: passed/failed/skipped |
| error_message | TEXT | | 错误信息 |
| steps_log | TEXT | | 步骤日志(JSON) |
| screenshots | TEXT | | 截图路径(JSON数组) |
| gif_path | TEXT | | GIF动画路径 |
| model | TEXT | | 使用的模型 |
| provider | TEXT | | 使用的提供商 |
| created_at | DATETIME | NOT NULL DEFAULT CURRENT_TIMESTAMP | 创建时间 |

**索引:**
- `idx_executions_project_id`: project_id
- `idx_executions_testcase_id`: testcase_id
- `idx_executions_status`: status
- `idx_executions_created_at`: created_at

---

### 5. 测试报告表 (test_reports)

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | 报告ID |
| project_id | INTEGER | NOT NULL, FOREIGN KEY -> projects(id) | 所属项目 |
| name | TEXT | NOT NULL | 报告名称 |
| status | TEXT | NOT NULL DEFAULT 'pending' | 状态: pending/running/completed |
| total_cases | INTEGER | NOT NULL DEFAULT 0 | 总用例数 |
| passed_cases | INTEGER | NOT NULL DEFAULT 0 | 通过数 |
| failed_cases | INTEGER | NOT NULL DEFAULT 0 | 失败数 |
| skipped_cases | INTEGER | NOT NULL DEFAULT 0 | 跳过数 |
| pass_rate | REAL | NOT NULL DEFAULT 0 | 通过率 |
| start_time | DATETIME | NOT NULL | 开始时间 |
| end_time | DATETIME | | 结束时间 |
| duration | INTEGER | | 执行时长(秒) |
| created_at | DATETIME | NOT NULL DEFAULT CURRENT_TIMESTAMP | 创建时间 |

**索引:**
- `idx_reports_project_id`: project_id
- `idx_reports_created_at`: created_at
- `idx_reports_status`: status

---

### 6. 报告用例关联表 (report_cases)

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | 关联ID |
| report_id | INTEGER | NOT NULL, FOREIGN KEY -> test_reports(id) | 报告ID |
| execution_id | TEXT | NOT NULL | 执行ID |
| testcase_id | INTEGER | NOT NULL | 用例ID |
| order_index | INTEGER | NOT NULL | 执行顺序 |

**索引:**
- `idx_report_cases_report_id`: report_id

---

### 7. 系统配置表 (system_configs)

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | 配置ID |
| key | TEXT | NOT NULL UNIQUE | 配置键 |
| value | TEXT | | 配置值 |
| description | TEXT | | 配置描述 |
| updated_at | DATETIME | NOT NULL DEFAULT CURRENT_TIMESTAMP | 更新时间 |

---

## ER图关系

```
projects (1) ----< (N) documents
projects (1) ----< (N) test_cases
documents (1) ----< (N) test_cases (可选)
projects (1) ----< (N) test_executions
test_cases (1) ----< (N) test_executions
test_cases (1) ----< (N) test_reports (通过report_cases关联)
```

---

## 初始化SQL

```sql
-- 创建项目表
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_projects_name ON projects(name);
CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);

-- 创建文档表
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_type TEXT NOT NULL,
    file_size INTEGER,
    extracted_text TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_documents_project_id ON documents(project_id);

-- 创建测试用例表
CREATE TABLE IF NOT EXISTS test_cases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    document_id INTEGER,
    name TEXT NOT NULL,
    description TEXT,
    precondition TEXT,
    steps TEXT NOT NULL,
    expected_result TEXT NOT NULL,
    priority TEXT NOT NULL DEFAULT 'medium',
    tags TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_test_cases_project_id ON test_cases(project_id);
CREATE INDEX IF NOT EXISTS idx_test_cases_priority ON test_cases(priority);

-- 创建测试执行表
CREATE TABLE IF NOT EXISTS test_executions (
    id TEXT PRIMARY KEY,
    project_id INTEGER NOT NULL,
    testcase_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    start_time DATETIME,
    end_time DATETIME,
    duration INTEGER,
    result TEXT,
    error_message TEXT,
    steps_log TEXT,
    screenshots TEXT,
    gif_path TEXT,
    model TEXT,
    provider TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (testcase_id) REFERENCES test_cases(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_executions_project_id ON test_executions(project_id);
CREATE INDEX IF NOT EXISTS idx_executions_testcase_id ON test_executions(testcase_id);
CREATE INDEX IF NOT EXISTS idx_executions_status ON test_executions(status);

-- 创建测试报告表
CREATE TABLE IF NOT EXISTS test_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    total_cases INTEGER NOT NULL DEFAULT 0,
    passed_cases INTEGER NOT NULL DEFAULT 0,
    failed_cases INTEGER NOT NULL DEFAULT 0,
    skipped_cases INTEGER NOT NULL DEFAULT 0,
    pass_rate REAL NOT NULL DEFAULT 0,
    start_time DATETIME NOT NULL,
    end_time DATETIME,
    duration INTEGER,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_reports_project_id ON test_reports(project_id);

-- 创建报告用例关联表
CREATE TABLE IF NOT EXISTS report_cases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id INTEGER NOT NULL,
    execution_id TEXT NOT NULL,
    testcase_id INTEGER NOT NULL,
    order_index INTEGER NOT NULL,
    FOREIGN KEY (report_id) REFERENCES test_reports(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_report_cases_report_id ON report_cases(report_id);

-- 创建系统配置表
CREATE TABLE IF NOT EXISTS system_configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT NOT NULL UNIQUE,
    value TEXT,
    description TEXT,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 插入默认配置
INSERT OR IGNORE INTO system_configs (key, value, description) VALUES
    ('default_model', 'qwen3.5-flash', '默认使用的模型'),
    ('default_provider', 'qwen', '默认模型提供商'),
    ('max_execution_time', '3600', '最大执行时间（秒）'),
    ('screenshot_enabled', 'true', '是否启用截图');
```

---

## 数据目录结构

```
backend/data/
├── testing_platform.db          # SQLite数据库文件
├── uploads/                     # 上传文件目录
│   └── documents/              # 需求文档
│       └── {project_id}/
│           ├── {document_id}.pdf
│           └── {document_id}.docx
└── screenshots/                # 测试截图
    └── {execution_id}/
        ├── step_1.png
        ├── step_2.png
        └── animation.gif
```
