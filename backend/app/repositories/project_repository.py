"""项目数据访问层"""

from typing import List, Optional, Dict, Any

from app.database import get_db_connection


class ProjectRepository:
    """项目数据访问对象"""

    def __init__(self):
        pass

    def get_all_active(self) -> List[Dict[str, Any]]:
        """获取所有活跃项目"""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM projects WHERE status = 'active' ORDER BY created_at DESC")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def get_by_id(self, project_id: int) -> Optional[Dict[str, Any]]:
        """根据 ID 获取项目"""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def create(self, name: str, description: Optional[str] = None) -> int:
        """创建项目"""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO projects (name, description) VALUES (?, ?)",
            (name, description)
        )
        conn.commit()
        project_id = cursor.lastrowid
        conn.close()
        return project_id

    def update(self, project_id: int, **kwargs) -> bool:
        """更新项目"""
        conn = get_db_connection()
        cursor = conn.cursor()

        updates = []
        params = []
        for key, value in kwargs.items():
            if value is not None:
                updates.append(f"{key} = ?")
                params.append(value)

        if updates:
            updates.append("updated_at = CURRENT_TIMESTAMP")
            params.append(project_id)
            cursor.execute(
                f"UPDATE projects SET {', '.join(updates)} WHERE id = ?",
                params
            )
            conn.commit()

        conn.close()
        return cursor.rowcount > 0

    def delete(self, project_id: int) -> bool:
        """删除项目"""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        conn.commit()
        deleted = cursor.rowcount > 0
        conn.close()
        return deleted

    def get_testcase_count(self, project_id: int) -> int:
        """获取项目的测试用例数量"""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) as count FROM test_cases WHERE project_id = ?",
            (project_id,)
        )
        count = cursor.fetchone()["count"]
        conn.close()
        return count

    def get_execution_count(self, project_id: int) -> int:
        """获取项目的执行数量"""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) as count FROM test_executions WHERE project_id = ?",
            (project_id,)
        )
        count = cursor.fetchone()["count"]
        conn.close()
        return count
