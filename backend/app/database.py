"""数据库初始化和连接管理"""

import sqlite3
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime

# 数据库路径
DB_DIR = Path(__file__).parent.parent / "data"
DB_PATH = DB_DIR / "testing_platform.db"

# 确保目录存在
DB_DIR.mkdir(parents=True, exist_ok=True)


def get_db_connection() -> sqlite3.Connection:
    """获取数据库连接 - 使用更短的锁超时"""
    conn = sqlite3.connect(
        str(DB_PATH),
        check_same_thread=False,
        detect_types=sqlite3.PARSE_DECLTYPES,
        timeout=10.0  # 设置10秒锁超时
    )
    conn.row_factory = sqlite3.Row

    # 设置 CURRENT_TIMESTAMP 使用本地时间而不是 UTC
    # 使用 WAL 模式以支持更好的并发
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")  # 平衡性能和安全性
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=10000")  # 10秒超时

    return conn


def init_database():
    """初始化数据库表"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 创建项目表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_projects_name ON projects(name)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status)")

    # 创建文档表
    cursor.execute("""
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
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_documents_project_id ON documents(project_id)")

    # 创建测试用例表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS test_cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            document_id INTEGER,
            name TEXT NOT NULL,
            description TEXT,
            priority TEXT NOT NULL DEFAULT 'P1',
            case_type TEXT NOT NULL DEFAULT '正向',
            precondition TEXT,
            steps TEXT NOT NULL,
            expected_result TEXT NOT NULL,
            actual_result TEXT,
            status TEXT NOT NULL DEFAULT '待测试',
            tester TEXT,
            test_date TEXT,
            tags TEXT,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
            FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE SET NULL
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_test_cases_project_id ON test_cases(project_id)")

    # 为已存在的表添加新字段（如果表已存在）
    try:
        cursor.execute("ALTER TABLE test_cases ADD COLUMN case_type TEXT DEFAULT '正向'")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE test_cases ADD COLUMN actual_result TEXT")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE test_cases ADD COLUMN tester TEXT")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE test_cases ADD COLUMN test_date TEXT")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE test_cases ADD COLUMN gif_path TEXT")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE test_cases ADD COLUMN script_path TEXT")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE test_cases ADD COLUMN network_path TEXT")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE test_cases ADD COLUMN execution_options TEXT")
    except:
        pass

    # 创建索引（在添加列之后）
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_test_cases_priority ON test_cases(priority)")
    try:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_test_cases_type ON test_cases(case_type)")
    except:
        pass
    try:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_test_cases_status ON test_cases(status)")
    except:
        pass

    # 创建测试执行表
    cursor.execute("""
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
            script_path TEXT,
            network_path TEXT,
            model TEXT,
            provider TEXT,
            final_answer TEXT,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
            FOREIGN KEY (testcase_id) REFERENCES test_cases(id) ON DELETE CASCADE
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_executions_project_id ON test_executions(project_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_executions_testcase_id ON test_executions(testcase_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_executions_status ON test_executions(status)")

    # 添加 final_answer 列（如果不存在）
    try:
        cursor.execute("ALTER TABLE test_executions ADD COLUMN final_answer TEXT")
    except:
        pass  # 列已存在
    try:
        cursor.execute("ALTER TABLE test_executions ADD COLUMN script_path TEXT")
    except:
        pass  # 列已存在
    try:
        cursor.execute("ALTER TABLE test_executions ADD COLUMN network_path TEXT")
    except:
        pass  # 列已存在

    # 创建测试报告表
    cursor.execute("""
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
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_reports_project_id ON test_reports(project_id)")

    # 创建报告用例关联表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS report_cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id INTEGER NOT NULL,
            execution_id TEXT NOT NULL,
            testcase_id INTEGER NOT NULL,
            order_index INTEGER NOT NULL,
            FOREIGN KEY (report_id) REFERENCES test_reports(id) ON DELETE CASCADE
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_report_cases_report_id ON report_cases(report_id)")

    # 创建缺陷分析表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS defect_analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            testcase_id INTEGER NOT NULL,
            execution_id TEXT NOT NULL,
            analysis_result TEXT NOT NULL,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (testcase_id) REFERENCES test_cases(id) ON DELETE CASCADE
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_defect_analyses_testcase_id ON defect_analyses(testcase_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_defect_analyses_execution_id ON defect_analyses(execution_id)")

    # 创建系统配置表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_configs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT NOT NULL UNIQUE,
            value TEXT,
            description TEXT,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 插入默认配置
    cursor.execute("""
        INSERT OR IGNORE INTO system_configs (key, value, description) VALUES
            ('default_model', 'qwen3.5-flash', '默认使用的模型'),
            ('default_provider', 'qwen', '默认模型提供商'),
            ('max_execution_time', '3600', '最大执行时间（秒）'),
            ('screenshot_enabled', 'true', '是否启用截图')
    """)

    conn.commit()
    conn.close()

    print(f"[OK] Database initialized: {DB_PATH}")


# 初始化数据库
init_database()
