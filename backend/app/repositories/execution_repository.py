"""执行记录数据访问层"""

import json
from typing import List, Optional, Dict, Any

from app.database import get_db_connection


class ExecutionRepository:
    """执行记录数据访问对象"""

    def __init__(self):
        pass

    def get_by_id(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """根据 ID 获取执行记录"""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT *,
                   datetime(created_at, 'localtime') as created_at_local,
                   datetime(start_time, 'localtime') as start_time_local,
                   datetime(end_time, 'localtime') as end_time_local
            FROM test_executions
            WHERE id = ?
        """, (execution_id,))
        row = cursor.fetchone()
        conn.close()
        return self._parse_row(dict(row)) if row else None

    def get_by_project(
        self,
        project_id: int,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None
    ) -> Dict[str, Any]:
        """获取项目的执行记录列表（分页）"""
        conn = get_db_connection()
        cursor = conn.cursor()

        conditions = ["te.project_id = ?"]
        params = [project_id]

        if status:
            conditions.append("te.status = ?")
            params.append(status)

        where_clause = " AND ".join(conditions)

        # 总数
        cursor.execute(f"SELECT COUNT(*) as total FROM test_executions te WHERE {where_clause}", params)
        total = cursor.fetchone()["total"]

        # 分页数据
        offset = (page - 1) * page_size
        params.extend([page_size, offset])

        cursor.execute(f"""
            SELECT te.*,
                   datetime(te.created_at, 'localtime') as created_at_local,
                   datetime(te.start_time, 'localtime') as start_time_local,
                   datetime(te.end_time, 'localtime') as end_time_local,
                   tc.name as testcase_name, tc.priority as testcase_priority
            FROM test_executions te
            LEFT JOIN test_cases tc ON te.testcase_id = tc.id
            WHERE {where_clause}
            ORDER BY COALESCE(te.start_time, te.created_at) DESC LIMIT ? OFFSET ?
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

    def get_latest_by_testcase(self, testcase_id: int) -> Optional[Dict[str, Any]]:
        """获取测试用例的最新执行记录"""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT te.*,
                   datetime(te.created_at, 'localtime') as created_at_local,
                   datetime(te.start_time, 'localtime') as start_time_local,
                   datetime(te.end_time, 'localtime') as end_time_local
            FROM test_executions te
            WHERE te.testcase_id = ?
            ORDER BY COALESCE(te.start_time, te.created_at) DESC
            LIMIT 1
        """, (testcase_id,))
        row = cursor.fetchone()
        conn.close()
        return self._parse_row(dict(row)) if row else None

    def create(self, data: Dict[str, Any]) -> str:
        """创建执行记录"""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO test_executions
            (id, project_id, testcase_id, status, start_time, end_time,
             duration, result, error_message, steps_log, screenshots,
             gif_path, model, provider, final_answer)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data.get("id"),
            data.get("project_id"),
            data.get("testcase_id"),
            data.get("status", "pending"),
            data.get("start_time"),
            data.get("end_time"),
            data.get("duration"),
            data.get("result"),
            data.get("error_message"),
            json.dumps(data.get("steps_log", []), ensure_ascii=False),
            json.dumps(data.get("screenshots", []), ensure_ascii=False),
            data.get("gif_path"),
            data.get("model"),
            data.get("provider"),
            data.get("final_answer")
        ))
        conn.commit()
        conn.close()
        return data.get("id")

    def update(self, execution_id: str, **kwargs) -> bool:
        """更新执行记录"""
        conn = get_db_connection()
        cursor = conn.cursor()

        updates = []
        params = []
        for key, value in kwargs.items():
            updates.append(f"{key} = ?")
            params.append(value)

        if updates:
            cursor.execute(
                f"UPDATE test_executions SET {', '.join(updates)} WHERE id = ?",
                params + [execution_id]
            )
            conn.commit()

        conn.close()
        return cursor.rowcount > 0

    def delete(self, execution_id: str) -> bool:
        """删除执行记录"""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM test_executions WHERE id = ?", (execution_id,))
        conn.commit()
        deleted = cursor.rowcount > 0
        conn.close()
        return deleted

    def batch_delete(self, ids: List[str]) -> int:
        """批量删除执行记录"""
        if not ids:
            return 0

        conn = get_db_connection()
        cursor = conn.cursor()
        placeholders = ",".join(["?"] * len(ids))
        cursor.execute(f"DELETE FROM test_executions WHERE id IN ({placeholders})", ids)
        conn.commit()
        deleted = cursor.rowcount
        conn.close()
        return deleted

    def update_status_running(self, execution_id: str) -> bool:
        """更新状态为运行中"""
        return self.update(execution_id, status="running", start_time="CURRENT_TIMESTAMP")

    def update_status_completed(
        self,
        execution_id: str,
        result: str,
        end_time: str = "CURRENT_TIMESTAMP",
        duration: int = 0,
        error_message: Optional[str] = None,
        steps_log: Optional[List] = None,
        screenshots: Optional[List[str]] = None,
        gif_path: Optional[str] = None,
        final_answer: Optional[str] = None
    ) -> bool:
        """更新状态为完成"""
        kwargs = {
            "status": "completed",
            "end_time": end_time,
            "result": result,
            "duration": duration
        }
        if error_message is not None:
            kwargs["error_message"] = error_message
        if steps_log is not None:
            kwargs["steps_log"] = json.dumps(steps_log, ensure_ascii=False)
        if screenshots is not None:
            kwargs["screenshots"] = json.dumps(screenshots, ensure_ascii=False)
        if gif_path is not None:
            kwargs["gif_path"] = gif_path
        if final_answer is not None:
            kwargs["final_answer"] = final_answer

        return self.update(execution_id, **kwargs)

    def update_status_failed(
        self,
        execution_id: str,
        error_message: str,
        end_time: str = "CURRENT_TIMESTAMP"
    ) -> bool:
        """更新状态为失败"""
        return self.update(
            execution_id,
            status="failed",
            end_time=end_time,
            error_message=error_message
        )

    def _parse_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """解析行数据，处理 JSON 字段和时间"""
        if not row:
            return row

        # 使用本地时间替换 UTC 时间
        if row.get("created_at_local"):
            row["created_at"] = row["created_at_local"]
        if row.get("start_time_local"):
            row["start_time"] = row["start_time_local"]
        if row.get("end_time_local"):
            row["end_time"] = row["end_time_local"]
        row.pop("created_at_local", None)
        row.pop("start_time_local", None)
        row.pop("end_time_local", None)

        # 处理 steps_log
        if row.get("steps_log"):
            try:
                row["steps_log"] = json.loads(row["steps_log"])
            except:
                row["steps_log"] = []

        # 处理 screenshots
        if row.get("screenshots"):
            try:
                row["screenshots"] = json.loads(row["screenshots"])
            except:
                row["screenshots"] = []

        return row
