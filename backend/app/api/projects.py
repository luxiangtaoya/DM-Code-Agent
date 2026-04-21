"""项目管理 API"""

from fastapi import APIRouter, HTTPException
from pathlib import Path
from typing import List

from app.database import get_db_connection
from app.models import ProjectCreate, ProjectUpdate, ApiResponse
from app.execution_service import logger

# 从主应用导入路由器
from app.api import api_router

# 数据目录
backend_dir = Path(__file__).parent.parent.parent
DATA_DIR = backend_dir / "data"
SCREENSHOT_DIR = DATA_DIR / "screenshots"


def get_project_testcase_count(project_id: int) -> int:
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


def get_project_execution_count(project_id: int) -> int:
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


@api_router.get("/projects", response_model=ApiResponse)
async def get_projects():
    """获取项目列表"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM projects WHERE status = 'active' ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()

    projects = []
    for row in rows:
        project = dict(row)
        project["test_case_count"] = get_project_testcase_count(project["id"])
        project["execution_count"] = get_project_execution_count(project["id"])
        projects.append(project)

    return ApiResponse(data=projects)


@api_router.post("/projects", response_model=ApiResponse)
async def create_project(request: ProjectCreate):
    """创建项目"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO projects (name, description) VALUES (?, ?)",
        (request.name, request.description)
    )
    conn.commit()
    project_id = cursor.lastrowid

    cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
    row = cursor.fetchone()
    conn.close()

    project = dict(row)
    project["test_case_count"] = 0
    project["execution_count"] = 0

    return ApiResponse(data=project)


@api_router.get("/projects/{project_id}", response_model=ApiResponse)
async def get_project(project_id: int):
    """获取项目详情"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="项目不存在")

    project = dict(row)
    project["test_case_count"] = get_project_testcase_count(project_id)
    project["execution_count"] = get_project_execution_count(project_id)

    return ApiResponse(data=project)


@api_router.put("/projects/{project_id}", response_model=ApiResponse)
async def update_project(project_id: int, request: ProjectUpdate):
    """更新项目"""
    conn = get_db_connection()
    cursor = conn.cursor()

    updates = []
    params = []

    if request.name is not None:
        updates.append("name = ?")
        params.append(request.name)
    if request.description is not None:
        updates.append("description = ?")
        params.append(request.description)
    if request.status is not None:
        updates.append("status = ?")
        params.append(request.status.value)

    if updates:
        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(project_id)
        cursor.execute(
            f"UPDATE projects SET {', '.join(updates)} WHERE id = ?",
            params
        )
        conn.commit()

    conn.close()
    return ApiResponse(data={"updated": True})


@api_router.delete("/projects/{project_id}", response_model=ApiResponse)
async def delete_project(project_id: int):
    """删除项目"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    conn.commit()
    conn.close()

    return ApiResponse(data={"deleted": True})
