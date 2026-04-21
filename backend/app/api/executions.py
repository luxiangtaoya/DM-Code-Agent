"""测试执行 API"""

import os
import json
import subprocess
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException

from app.database import get_db_connection
from app.models import BatchExecuteRequest, BatchDeleteExecutionsRequest, ApiResponse
from app.execution_service import execute_single_testcase, get_task_scheduler, logger

from app.api import api_router

# 数据目录
backend_dir = Path(__file__).parent.parent.parent
DATA_DIR = backend_dir / "data"
SCREENSHOT_DIR = DATA_DIR / "screenshots"


@api_router.post("/testcases/batch-execute", response_model=ApiResponse)
async def batch_execute_testcases(request: BatchExecuteRequest):
    """批量执行测试用例 - 将多个用例状态设置为'等待执行'"""
    conn = get_db_connection()
    cursor = conn.cursor()

    execution_options = json.dumps({
        "model": request.model if hasattr(request, 'model') else "qwen3.5-flash",
        "provider": request.provider if hasattr(request, 'provider') else "qwen",
        "enable_screenshots": request.enable_screenshots if hasattr(request, 'enable_screenshots') else True,
        "enable_network_trace": request.enable_network_trace if hasattr(request, 'enable_network_trace') else False,
        "enable_script": request.enable_script if hasattr(request, 'enable_script') else True,
    }, ensure_ascii=False)

    updated_count = 0
    for testcase_id in request.testcase_ids:
        cursor.execute("""
            UPDATE test_cases
            SET status = '等待执行',
                execution_options = ?
            WHERE id = ?
        """, (execution_options, testcase_id))
        updated_count += cursor.rowcount

    conn.commit()
    conn.close()

    logger.info(f"[API] 批量执行：{updated_count} 个测试用例已加入队列")

    return ApiResponse(data={
        "updated_count": updated_count,
        "message": f"{updated_count} 个测试用例已加入执行队列"
    })


@api_router.get("/testcases/{testcase_id}/status", response_model=ApiResponse)
async def get_testcase_status(testcase_id: int):
    """获取测试用例状态"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM test_cases WHERE id = ?", (testcase_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="测试用例不存在")

    return ApiResponse(data=dict(row))


@api_router.get("/executions/{execution_id}", response_model=ApiResponse)
async def get_execution_status(execution_id: str):
    """获取执行状态 - 从数据库获取"""
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

    if not row:
        raise HTTPException(status_code=404, detail="执行记录不存在")

    execution = dict(row)
    if execution.get("created_at_local"):
        execution["created_at"] = execution["created_at_local"]
    if execution.get("start_time_local"):
        execution["start_time"] = execution["start_time_local"]
    if execution.get("end_time_local"):
        execution["end_time"] = execution["end_time_local"]
    execution.pop("created_at_local", None)
    execution.pop("start_time_local", None)
    execution.pop("end_time_local", None)

    if execution.get("steps_log"):
        try:
            execution["steps_log"] = json.loads(execution["steps_log"])
        except:
            execution["steps_log"] = []

    return ApiResponse(data=execution)


@api_router.get("/projects/{project_id}/executions", response_model=ApiResponse)
async def get_project_executions(
    project_id: int,
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None
):
    """获取项目的执行记录列表"""
    conn = get_db_connection()
    cursor = conn.cursor()

    conditions = ["te.project_id = ?"]
    params = [project_id]

    if status:
        conditions.append("te.status = ?")
        params.append(status)

    where_clause = " AND ".join(conditions)

    cursor.execute(f"SELECT COUNT(*) as total FROM test_executions te WHERE {where_clause}", params)
    total = cursor.fetchone()["total"]

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

    executions = []
    for row in rows:
        execution = dict(row)
        if execution.get("created_at_local"):
            execution["created_at"] = execution["created_at_local"]
        if execution.get("start_time_local"):
            execution["start_time"] = execution["start_time_local"]
        if execution.get("end_time_local"):
            execution["end_time"] = execution["end_time_local"]
        execution.pop("created_at_local", None)
        execution.pop("start_time_local", None)
        execution.pop("end_time_local", None)
        execution["time"] = execution.get("start_time") or execution.get("created_at")
        if execution.get("steps_log"):
            try:
                execution["steps_log"] = json.loads(execution["steps_log"])
            except:
                execution["steps_log"] = []
        executions.append(execution)

    return ApiResponse(data={
        "items": executions,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size
    })


@api_router.get("/executions/{execution_id}/gif", response_model=ApiResponse)
async def get_execution_gif(execution_id: str):
    """获取执行生成的 GIF"""
    from fastapi.responses import FileResponse

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT gif_path FROM test_executions WHERE id = ?", (execution_id,))
    row = cursor.fetchone()
    conn.close()

    if not row or not row["gif_path"]:
        raise HTTPException(status_code=404, detail="GIF 不存在")

    gif_path = row["gif_path"]
    if not os.path.exists(gif_path):
        raise HTTPException(status_code=404, detail="GIF 文件不存在")

    return FileResponse(
        gif_path,
        media_type="image/gif",
        filename=f"{execution_id}.gif"
    )


@api_router.delete("/executions/{execution_id}", response_model=ApiResponse)
async def delete_execution(execution_id: str):
    """删除单条执行记录"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM test_executions WHERE id = ?", (execution_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="执行记录不存在")

    cursor.execute("DELETE FROM test_executions WHERE id = ?", (execution_id,))
    conn.commit()
    conn.close()

    logger.info(f"[API] 删除执行记录：execution_id={execution_id}")

    return ApiResponse(data={"deleted": True})


@api_router.delete("/executions", response_model=ApiResponse)
async def batch_delete_executions(request: BatchDeleteExecutionsRequest):
    """批量删除执行记录"""
    if not request.ids:
        return ApiResponse(data={"deleted_count": 0})

    conn = get_db_connection()
    cursor = conn.cursor()

    placeholders = ",".join(["?"] * len(request.ids))
    cursor.execute(f"DELETE FROM test_executions WHERE id IN ({placeholders})", request.ids)
    conn.commit()
    deleted_count = cursor.rowcount
    conn.close()

    logger.info(f"[API] 批量删除执行记录：{deleted_count} 条")

    return ApiResponse(data={"deleted_count": deleted_count})


@api_router.get("/testcases/{testcase_id}/latest-execution", response_model=ApiResponse)
async def get_testcase_latest_execution(testcase_id: int):
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

    if not row:
        return ApiResponse(data=None)

    execution = dict(row)
    if execution.get("created_at_local"):
        execution["created_at"] = execution["created_at_local"]
    if execution.get("start_time_local"):
        execution["start_time"] = execution["start_time_local"]
    if execution.get("end_time_local"):
        execution["end_time"] = execution["end_time_local"]
    execution.pop("created_at_local", None)
    execution.pop("start_time_local", None)
    execution.pop("end_time_local", None)

    if execution.get("steps_log"):
        try:
            execution["steps_log"] = json.loads(execution["steps_log"])
        except:
            execution["steps_log"] = []

    return ApiResponse(data=execution)
