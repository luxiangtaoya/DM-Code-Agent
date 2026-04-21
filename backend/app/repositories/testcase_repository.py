"""测试用例数据访问层"""

import json
from typing import List, Optional, Dict, Any

from app.database import get_db_connection


class TestCaseRepository:
    """测试用例数据访问对象"""

    def __init__(self):
        pass

    def get_by_id(self, testcase_id: int) -> Optional[Dict[str, Any]]:
        """根据 ID 获取测试用例"""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM test_cases WHERE id = ?", (testcase_id,))
        row = cursor.fetchone()
        conn.close()
        return self._parse_row(dict(row)) if row else None

    def get_by_project(
        self,
        project_id: int,
        page: int = 1,
        page_size: int = 20,
        priority: Optional[str] = None,
        case_type: Optional[str] = None,
        status: Optional[str] = None,
        keyword: Optional[str] = None
    ) -> Dict[str, Any]:
        """获取项目的测试用例列表（分页）"""
        conn = get_db_connection()
        cursor = conn.cursor()

        conditions = ["project_id = ?"]
        params = [project_id]

        if priority:
            conditions.append("priority = ?")
            params.append(priority)
        if case_type:
            conditions.append("case_type = ?")
            params.append(case_type)
        if status:
            conditions.append("status = ?")
            params.append(status)
        if keyword:
            conditions.append("(name LIKE ? OR description LIKE ?)")
            params.extend([f"%{keyword}%", f"%{keyword}%"])

        where_clause = " AND ".join(conditions)

        # 总数
        cursor.execute(f"SELECT COUNT(*) as total FROM test_cases WHERE {where_clause}", params)
        total = cursor.fetchone()["total"]

        # 分页数据
        offset = (page - 1) * page_size
        params.extend([page_size, offset])
        cursor.execute(f"""
            SELECT * FROM test_cases WHERE {where_clause}
            ORDER BY created_at DESC LIMIT ? OFFSET ?
        """, params)
        rows = cursor.fetchall()
        conn.close()

        items = [self._parse_row(dict(row)) for row in rows]

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        }

    def create(self, project_id: int, data: Dict[str, Any]) -> int:
        """创建测试用例"""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO test_cases
            (project_id, name, description, priority, case_type, precondition,
             steps, expected_result, actual_result, status, tester, test_date, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            project_id,
            data.get("name"),
            data.get("description"),
            data.get("priority", "P1"),
            data.get("case_type", "正向"),
            data.get("precondition"),
            data.get("steps"),
            data.get("expected_result"),
            data.get("actual_result"),
            data.get("status", "待测试"),
            data.get("tester"),
            data.get("test_date"),
            json.dumps(data.get("tags", []), ensure_ascii=False)
        ))
        conn.commit()
        case_id = cursor.lastrowid
        conn.close()
        return case_id

    def update(self, testcase_id: int, **kwargs) -> bool:
        """更新测试用例"""
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
            params.append(testcase_id)
            cursor.execute(
                f"UPDATE test_cases SET {', '.join(updates)} WHERE id = ?",
                params
            )
            conn.commit()

        conn.close()
        return cursor.rowcount > 0

    def delete(self, testcase_id: int) -> bool:
        """删除测试用例"""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM test_cases WHERE id = ?", (testcase_id,))
        conn.commit()
        deleted = cursor.rowcount > 0
        conn.close()
        return deleted

    def batch_delete(self, ids: List[int]) -> int:
        """批量删除测试用例"""
        if not ids:
            return 0

        conn = get_db_connection()
        cursor = conn.cursor()
        placeholders = ",".join(["?"] * len(ids))
        cursor.execute(f"DELETE FROM test_cases WHERE id IN ({placeholders})", ids)
        conn.commit()
        deleted = cursor.rowcount
        conn.close()
        return deleted

    def set_status_pending(self, ids: List[int]) -> int:
        """批量设置状态为待测试"""
        conn = get_db_connection()
        cursor = conn.cursor()
        placeholders = ",".join(["?"] * len(ids))
        cursor.execute(
            f"UPDATE test_cases SET status = '待测试' WHERE id IN ({placeholders})",
            ids
        )
        conn.commit()
        updated = cursor.rowcount
        conn.close()
        return updated

    def set_waiting_execution(self, ids: List[int], execution_options: str) -> int:
        """批量设置状态为等待执行"""
        conn = get_db_connection()
        cursor = conn.cursor()
        placeholders = ",".join(["?"] * len(ids))
        cursor.execute("""
            UPDATE test_cases
            SET status = '等待执行', execution_options = ?
            WHERE id IN ({placeholders})
        """.format(placeholders=placeholders), [execution_options] + ids)
        conn.commit()
        updated = cursor.rowcount
        conn.close()
        return updated

    def _parse_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """解析行数据，处理 JSON 字段"""
        if not row:
            return row

        # 处理 steps
        try:
            row["steps"] = json.loads(row["steps"])
        except:
            if row.get("steps"):
                row["steps"] = row["steps"].split('\n')
            else:
                row["steps"] = []

        # 处理 tags
        try:
            row["tags"] = json.loads(row["tags"]) if row.get("tags") else []
        except:
            row["tags"] = []

        return row
