"""FastAPI 主应用 - AI自动化测试平台"""

import os
import sys
import uuid
import json
import logging
import asyncio
import socket
import subprocess
import threading
import psutil
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, APIRouter, UploadFile, File, Form, BackgroundTasks, HTTPException
from contextlib import asynccontextmanager
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

# 添加dm_agent路径
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# 导入应用模块
from app.database import get_db_connection, init_database
from app.execution_service import (
    get_logs as service_get_logs,
    execute_single_testcase,
    get_task_scheduler,
    start_task_scheduler,
    AgentPool,
    get_agent_pool,
)
from app.models import *
from app.services import DocumentParser, TestCaseGenerator
from app.services.excel_parser import ExcelParser

# 配置全局日志
from dm_agent.logger import setup_global_logging
setup_global_logging(logging.INFO)

logger = logging.getLogger(__name__)


# ==================== 创建FastAPI应用 ====================

app = FastAPI(
    title="AI自动化测试平台",
    description="基于Agent的智能化测试平台",
    version="1.0.0"
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 创建API路由器
api_router = APIRouter(prefix="/api/v1", tags=["API"])

# 数据目录
DATA_DIR = backend_dir / "data"
UPLOAD_DIR = DATA_DIR / "uploads" / "documents"
SCREENSHOT_DIR = DATA_DIR / "screenshots"

# 确保目录存在
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

# 挂载静态文件目录（用于访问 GIF 截图）
app.mount("/screenshots", StaticFiles(directory=str(SCREENSHOT_DIR)), name="screenshots")


# ==================== 数据库操作函数 ====================

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


# ==================== 项目管理API ====================

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

    # 获取完整的项目信息
    cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
    row = cursor.fetchone()
    conn.close()

    project = dict(row)
    project["test_case_count"] = 0
    project["execution_count"] = 0

    # 调试输出
    print(f"DEBUG: project object = {project}")

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


# ==================== 文档管理API ====================

@api_router.post("/projects/{project_id}/documents", response_model=ApiResponse)
async def upload_document(
    project_id: int,
    file: UploadFile = File(...),
    title: Optional[str] = Form(None)
):
    """上传需求文档"""
    # 验证项目存在
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM projects WHERE id = ?", (project_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="项目不存在")

    # 验证文件类型
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in [".pdf", ".docx", ".doc"]:
        conn.close()
        raise HTTPException(status_code=400, detail="不支持的文件格式")

    # 创建项目目录
    project_dir = UPLOAD_DIR / str(project_id)
    project_dir.mkdir(exist_ok=True)

    # 保存文件
    file_id = str(uuid.uuid4())
    file_path = project_dir / f"{file_id}{file_ext}"

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    # 提取文本
    try:
        extracted_text = extract_text_from_file(str(file_path))
    except Exception as e:
        os.remove(file_path)
        conn.close()
        raise HTTPException(status_code=400, detail=f"文档解析失败: {str(e)}")

    # 保存到数据库
    cursor.execute("""
        INSERT INTO documents (project_id, title, file_path, file_type, file_size, extracted_text)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        project_id,
        title or file.filename,
        str(file_path),
        file_ext[1:],
        len(content),
        extracted_text
    ))
    conn.commit()
    doc_id = cursor.lastrowid
    conn.close()

    return ApiResponse(data={
        "id": doc_id,
        "project_id": project_id,
        "title": title or file.filename,
        "file_type": file_ext[1:],
        "file_size": len(content),
        "extracted_text": extracted_text
    })


@api_router.get("/projects/{project_id}/documents", response_model=ApiResponse)
async def get_documents(project_id: int):
    """获取项目的文档列表"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM documents WHERE project_id = ? ORDER BY created_at DESC",
        (project_id,)
    )
    rows = cursor.fetchall()
    conn.close()

    documents = [dict(row) for row in rows]
    return ApiResponse(data=documents)


@api_router.delete("/documents/{document_id}", response_model=ApiResponse)
async def delete_document(document_id: int):
    """删除文档"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 获取文件路径
    cursor.execute("SELECT file_path FROM documents WHERE id = ?", (document_id,))
    row = cursor.fetchone()
    if row:
        file_path = row["file_path"]
        if os.path.exists(file_path):
            os.remove(file_path)

    cursor.execute("DELETE FROM documents WHERE id = ?", (document_id,))
    conn.commit()
    conn.close()

    return ApiResponse(data={"deleted": True})


# ==================== 测试用例API ====================

@api_router.post("/documents/{document_id}/generate-testcases", response_model=ApiResponse)
async def generate_testcases(document_id: int, request: GenerateTestCasesRequest):
    """AI生成测试用例"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM documents WHERE id = ?", (document_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="文档不存在")

    document = dict(row)
    if not document["extracted_text"]:
        raise HTTPException(status_code=400, detail="文档内容为空")

    try:
        # 创建LLM客户端
        from dm_agent import create_llm_client
        client = create_llm_client(
            provider=request.provider,
            api_key=os.getenv("API_KEY"),
            model=request.model,
            base_url=os.getenv("BASE_URL", ""),
        )

        # 生成测试用例
        generator = TestCaseGenerator(client)
        cases = generator.generate_from_document(
            document_text=document["extracted_text"],
            document_title=document["title"],
            max_cases=request.max_cases
        )

        return ApiResponse(data={
            "document_id": document_id,
            "generated_cases": [case.__dict__ for case in cases],
            "count": len(cases)
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成测试用例失败: {str(e)}")


@api_router.post("/projects/{project_id}/testcases", response_model=ApiResponse)
async def save_testcase(project_id: int, request: TestCaseCreate):
    """保存测试用例"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO test_cases
        (project_id, name, description, priority, case_type, precondition,
         steps, expected_result, actual_result, status, tester, test_date, tags)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        project_id,
        request.name,
        request.description,
        request.priority.value,
        request.case_type.value,
        request.precondition,
        request.steps,
        request.expected_result,
        request.actual_result,
        request.status.value,
        request.tester,
        request.test_date,
        json.dumps(request.tags or [], ensure_ascii=False)
    ))
    conn.commit()
    case_id = cursor.lastrowid
    conn.close()

    return ApiResponse(data={"id": case_id, "name": request.name})


@api_router.post("/projects/{project_id}/testcases/batch", response_model=ApiResponse)
async def batch_save_testcases(project_id: int, cases: List[TestCaseCreate]):
    """批量保存测试用例"""
    conn = get_db_connection()
    cursor = conn.cursor()

    saved_cases = []
    for case in cases:
        cursor.execute("""
            INSERT INTO test_cases
            (project_id, name, description, priority, case_type, precondition,
             steps, expected_result, actual_result, status, tester, test_date, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            project_id,
            case.name,
            case.description,
            case.priority.value,
            case.case_type.value,
            case.precondition,
            case.steps,
            case.expected_result,
            case.actual_result,
            case.status.value,
            case.tester,
            case.test_date,
            json.dumps(case.tags or [], ensure_ascii=False)
        ))
        saved_cases.append({"id": cursor.lastrowid, "name": case.name})

    conn.commit()
    conn.close()

    return ApiResponse(data=saved_cases)


@api_router.post("/projects/{project_id}/testcases/import/excel", response_model=ApiResponse)
async def import_testcases_from_excel(
    project_id: int,
    file: UploadFile = File(..., description="Excel文件")
):
    """从Excel导入测试用例"""
    # 检查文件类型
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="只支持Excel文件格式(.xlsx, .xls)")

    # 保存上传的文件
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = UPLOAD_DIR / f"testcases_import_{project_id}_{timestamp}_{file.filename}"

    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    try:
        # 解析Excel
        test_cases_data = ExcelParser.parse_test_cases(str(file_path))

        if not test_cases_data:
            raise HTTPException(status_code=400, detail="Excel文件中没有找到有效的测试用例")

        # 批量保存到数据库
        conn = get_db_connection()
        cursor = conn.cursor()

        saved_cases = []
        for case_data in test_cases_data:
            cursor.execute("""
                INSERT INTO test_cases
                (project_id, name, description, priority, case_type, precondition,
                 steps, expected_result, actual_result, status, tester, test_date, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                project_id,
                case_data.get("name"),
                case_data.get("description"),
                case_data.get("priority", "P1"),
                case_data.get("case_type", "正向"),
                case_data.get("precondition"),
                case_data.get("steps", ""),
                case_data.get("expected_result", ""),
                case_data.get("actual_result"),
                case_data.get("status", "待测试"),
                case_data.get("tester"),
                case_data.get("test_date"),
                json.dumps(case_data.get("tags", []), ensure_ascii=False)
            ))
            saved_cases.append({"id": cursor.lastrowid, "name": case_data.get("name")})

        conn.commit()
        conn.close()

        return ApiResponse(data={
            "message": f"成功导入 {len(saved_cases)} 条测试用例",
            "imported_count": len(saved_cases),
            "test_cases": saved_cases
        })

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导入失败: {str(e)}")


@api_router.get("/testcases/export/template")
async def download_excel_template():
    """下载Excel导入模板"""
    print("DEBUG: Template endpoint called!")  # Debug output
    from fastapi.responses import Response

    excel_data = ExcelParser.generate_excel_template()
    print(f"DEBUG: Generated excel data size: {len(excel_data)}")  # Debug output

    return Response(
        content=excel_data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": "attachment; filename=testcase_import_template.xlsx"
        }
    )


@api_router.get("/projects/{project_id}/testcases", response_model=ApiResponse)
async def get_testcases(
    project_id: int,
    page: int = 1,
    page_size: int = 20,
    priority: Optional[str] = None,
    case_type: Optional[str] = None,
    status: Optional[str] = None,
    keyword: Optional[str] = None
):
    """获取项目的测试用例列表"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 构建查询条件
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

    # 获取总数
    cursor.execute(f"SELECT COUNT(*) as total FROM test_cases WHERE {where_clause}", params)
    total = cursor.fetchone()["total"]

    # 获取分页数据
    offset = (page - 1) * page_size
    params.extend([page_size, offset])

    cursor.execute(f"""
        SELECT * FROM test_cases WHERE {where_clause}
        ORDER BY created_at DESC LIMIT ? OFFSET ?
    """, params)
    rows = cursor.fetchall()
    conn.close()

    cases = []
    for row in rows:
        case = dict(row)
        # Handle steps - may be string or JSON-encoded list
        try:
            case["steps"] = json.loads(case["steps"])
        except:
            # If steps is a plain string, convert to list (split by newlines)
            if case["steps"]:
                case["steps"] = case["steps"].split('\n')
            else:
                case["steps"] = []
        # Handle tags
        try:
            case["tags"] = json.loads(case["tags"]) if case["tags"] else []
        except:
            case["tags"] = []
        cases.append(case)

    return ApiResponse(data={
        "items": cases,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size
    })


@api_router.get("/testcases/{testcase_id}", response_model=ApiResponse)
async def get_testcase(testcase_id: int):
    """获取测试用例详情"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM test_cases WHERE id = ?", (testcase_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="测试用例不存在")

    case = dict(row)
    # Handle steps - may be string or JSON-encoded list
    try:
        case["steps"] = json.loads(case["steps"])
    except:
        if case["steps"]:
            case["steps"] = case["steps"].split('\n')
        else:
            case["steps"] = []
    # Handle tags
    try:
        case["tags"] = json.loads(case["tags"]) if case["tags"] else []
    except:
        case["tags"] = []

    return ApiResponse(data=case)


@api_router.put("/testcases/{testcase_id}", response_model=ApiResponse)
async def update_testcase(testcase_id: int, request: TestCaseCreate):
    """更新测试用例"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 检查测试用例是否存在
    cursor.execute("SELECT id FROM test_cases WHERE id = ?", (testcase_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="测试用例不存在")

    # 更新测试用例
    cursor.execute("""
        UPDATE test_cases
        SET name = ?, description = ?, priority = ?, case_type = ?,
            precondition = ?, steps = ?, expected_result = ?,
            actual_result = ?, status = ?, tester = ?, test_date = ?, tags = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (
        request.name,
        request.description,
        request.priority.value,
        request.case_type.value,
        request.precondition,
        request.steps,
        request.expected_result,
        request.actual_result,
        request.status.value,
        request.tester,
        request.test_date,
        json.dumps(request.tags or [], ensure_ascii=False),
        testcase_id
    ))
    conn.commit()
    conn.close()

    return ApiResponse(data={"updated": True, "id": testcase_id})


@api_router.delete("/testcases/{testcase_id}", response_model=ApiResponse)
async def delete_testcase(testcase_id: int):
    """删除测试用例"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM test_cases WHERE id = ?", (testcase_id,))
    conn.commit()
    conn.close()

    return ApiResponse(data={"deleted": True})


@api_router.delete("/testcases", response_model=ApiResponse)
async def batch_delete_testcases(request: BatchDeleteRequest):
    """批量删除测试用例"""
    if not request.ids:
        return ApiResponse(data={"deleted_count": 0})

    conn = get_db_connection()
    cursor = conn.cursor()

    placeholders = ",".join(["?"] * len(request.ids))
    cursor.execute(
        f"DELETE FROM test_cases WHERE id IN ({placeholders})",
        request.ids
    )
    conn.commit()
    deleted = cursor.rowcount
    conn.close()

    return ApiResponse(data={"deleted_count": deleted})


# ==================== 测试执行API ====================

@api_router.post("/testcases/batch-execute", response_model=ApiResponse)
async def batch_execute_testcases(
    request: BatchExecuteRequest
):
    """批量执行测试用例 - 将多个用例状态设置为'等待执行'"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 构建执行选项 JSON
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
    # 使用本地时间替换 UTC 时间
    if execution.get("created_at_local"):
        execution["created_at"] = execution["created_at_local"]
    if execution.get("start_time_local"):
        execution["start_time"] = execution["start_time_local"]
    if execution.get("end_time_local"):
        execution["end_time"] = execution["end_time_local"]
    # 移除临时字段
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

    # 构建查询条件
    conditions = ["te.project_id = ?"]
    params = [project_id]

    if status:
        conditions.append("te.status = ?")
        params.append(status)

    where_clause = " AND ".join(conditions)

    # 获取总数
    cursor.execute(f"SELECT COUNT(*) as total FROM test_executions te WHERE {where_clause}", params)
    total = cursor.fetchone()["total"]

    # 获取分页数据
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
        # 使用本地时间替换 UTC 时间
        if execution.get("created_at_local"):
            execution["created_at"] = execution["created_at_local"]
        if execution.get("start_time_local"):
            execution["start_time"] = execution["start_time_local"]
        if execution.get("end_time_local"):
            execution["end_time"] = execution["end_time_local"]
        # 移除临时字段
        execution.pop("created_at_local", None)
        execution.pop("start_time_local", None)
        execution.pop("end_time_local", None)
        # 优先使用 start_time 作为时间，如果没有则使用 created_at
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


@api_router.get("/executions/{execution_id}/gif")
async def get_execution_gif(execution_id: str):
    """获取执行生成的GIF"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT gif_path FROM test_executions WHERE id = ?", (execution_id,))
    row = cursor.fetchone()
    conn.close()

    if not row or not row["gif_path"]:
        raise HTTPException(status_code=404, detail="GIF不存在")

    gif_path = row["gif_path"]
    if not os.path.exists(gif_path):
        raise HTTPException(status_code=404, detail="GIF文件不存在")

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
    
    # 检查记录是否存在
    cursor.execute("SELECT id FROM test_executions WHERE id = ?", (execution_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="执行记录不存在")
    
    # 删除记录
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
    # 使用本地时间替换 UTC 时间
    if execution.get("created_at_local"):
        execution["created_at"] = execution["created_at_local"]
    if execution.get("start_time_local"):
        execution["start_time"] = execution["start_time_local"]
    if execution.get("end_time_local"):
        execution["end_time"] = execution["end_time_local"]
    # 移除临时字段
    execution.pop("created_at_local", None)
    execution.pop("start_time_local", None)
    execution.pop("end_time_local", None)

    if execution.get("steps_log"):
        try:
            execution["steps_log"] = json.loads(execution["steps_log"])
        except:
            execution["steps_log"] = []

    return ApiResponse(data=execution)


# ==================== 统计报告API ====================

@api_router.get("/projects/{project_id}/reports/statistics", response_model=ApiResponse)
async def get_project_statistics(
    project_id: int,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    status: Optional[str] = None
):
    """获取项目统计数据"""
    from app.database import get_db_connection

    conn = get_db_connection()
    cursor = conn.cursor()

    # 构建 WHERE 条件
    where_conditions = ["te.project_id = ?", "te.status IN ('completed', 'failed')"]
    params = [project_id]

    if start_date:
        where_conditions.append("DATE(te.end_time, 'localtime') >= ?")
        params.append(start_date)

    if end_date:
        where_conditions.append("DATE(te.end_time, 'localtime') <= ?")
        params.append(end_date)

    if status:
        where_conditions.append("te.result = ?")
        params.append(status)

    where_clause = " AND ".join(where_conditions)

    # 使用窗口函数获取每个测试用例的最新执行记录
    query = f"""
        SELECT * FROM (
            SELECT
                te.id as execution_id,
                te.testcase_id,
                te.status,
                te.result,
                te.duration,
                te.end_time,
                te.final_answer,
                tc.name as testcase_name,
                tc.description as testcase_description,
                tc.steps as testcase_steps,
                tc.expected_result as testcase_expected_result,
                ROW_NUMBER() OVER (PARTITION BY te.testcase_id ORDER BY te.created_at DESC) as rn
            FROM test_executions te
            LEFT JOIN test_cases tc ON te.testcase_id = tc.id
            WHERE {where_clause}
        )
        WHERE rn = 1
        ORDER BY end_time DESC
    """

    cursor.execute(query, params)
    rows = cursor.fetchall()

    # 统计概览
    total = len(rows)
    passed = sum(1 for r in rows if r['result'] == 'passed')
    failed = sum(1 for r in rows if r['status'] == 'completed' and r['result'] == 'failed')
    error = sum(1 for r in rows if r['status'] == 'failed')

    summary = {
        "total": total,
        "passed": passed,
        "failed": failed,
        "error": error
    }

    # 状态分布
    status_stats = {
        "labels": ["执行通过", "执行不通过", "执行错误"],
        "data": [passed, failed, error]
    }

    # 执行时间分布（按执行耗时区间）
    execution_time_ranges = {
        "0-10s": 0,
        "10-30s": 0,
        "30-60s": 0,
        "60-120s": 0,
        "120-180s": 0,
        "180-300s": 0,
        "300-600s": 0,
        "600s+": 0
    }

    for row in rows:
        duration = row['duration'] or 0
        if duration <= 10:
            execution_time_ranges["0-10s"] += 1
        elif duration <= 30:
            execution_time_ranges["10-30s"] += 1
        elif duration <= 60:
            execution_time_ranges["30-60s"] += 1
        elif duration <= 120:
            execution_time_ranges["60-120s"] += 1
        elif duration <= 180:
            execution_time_ranges["120-180s"] += 1
        elif duration <= 300:
            execution_time_ranges["180-300s"] += 1
        elif duration <= 600:
            execution_time_ranges["300-600s"] += 1
        else:
            execution_time_ranges["600s+"] += 1

    execution_time_stats = execution_time_ranges

    # 步骤数分布（更详细的区间）
    step_ranges = {
        "1-3步": 0,
        "4-6步": 0,
        "7-10步": 0,
        "11-15步": 0,
        "16-20步": 0,
        "21-30步": 0,
        "30步+": 0
    }

    for row in rows:
        cursor.execute("SELECT steps_log FROM test_executions WHERE id = ?", (row['execution_id'],))
        steps_row = cursor.fetchone()
        if steps_row and steps_row['steps_log']:
            try:
                steps = json.loads(steps_row['steps_log'])
                step_count = len(steps)
                if step_count <= 3:
                    step_ranges["1-3步"] += 1
                elif step_count <= 6:
                    step_ranges["4-6步"] += 1
                elif step_count <= 10:
                    step_ranges["7-10步"] += 1
                elif step_count <= 15:
                    step_ranges["11-15步"] += 1
                elif step_count <= 20:
                    step_ranges["16-20步"] += 1
                elif step_count <= 30:
                    step_ranges["21-30步"] += 1
                else:
                    step_ranges["30步+"] += 1
            except:
                pass

    step_count_stats = step_ranges

    # 耗时分布（更细的区间划分）
    duration_ranges = {
        "0-10s": 0,
        "10-30s": 0,
        "30-60s": 0,
        "60-120s": 0,
        "120-180s": 0,
        "180-300s": 0,
        "300-600s": 0,
        "600s+": 0
    }

    for row in rows:
        duration = row['duration'] or 0
        if duration <= 10:
            duration_ranges["0-10s"] += 1
        elif duration <= 30:
            duration_ranges["10-30s"] += 1
        elif duration <= 60:
            duration_ranges["30-60s"] += 1
        elif duration <= 120:
            duration_ranges["60-120s"] += 1
        elif duration <= 180:
            duration_ranges["120-180s"] += 1
        elif duration <= 300:
            duration_ranges["180-300s"] += 1
        elif duration <= 600:
            duration_ranges["300-600s"] += 1
        else:
            duration_ranges["600s+"] += 1

    duration_stats = duration_ranges

    # 缺陷列表（执行不通过的用例）
    defects = []
    for row in rows:
        # 执行不通过：status='completed' 且 result='failed'
        # 执行错误：status='failed'
        if (row['status'] == 'completed' and row['result'] == 'failed') or row['status'] == 'failed':
            # 获取分析次数
            cursor.execute(
                "SELECT COUNT(*) as count FROM defect_analyses WHERE testcase_id = ?",
                (row['testcase_id'],)
            )
            analysis_count_row = cursor.fetchone()
            analysis_count = analysis_count_row['count'] if analysis_count_row else 0

            # 确定状态显示
            status_text = "执行不通过" if (row['status'] == 'completed' and row['result'] == 'failed') else "执行失败"

            defects.append({
                "testcase_id": row['testcase_id'],
                "name": row['testcase_name'],
                "status": status_text,
                "duration": row['duration'] or 0,
                "final_answer": row['final_answer'] or "",
                "execution_id": row['execution_id'],
                "analysis_count": analysis_count
            })

    conn.close()

    return ApiResponse(data={
        "summary": summary,
        "status_stats": status_stats,
        "execution_time_stats": execution_time_stats,
        "step_count_stats": step_count_stats,
        "duration_stats": duration_stats,
        "defects": defects
    })


@api_router.post("/testcases/{testcase_id}/analyze-defect", response_model=ApiResponse)
async def analyze_defect(testcase_id: int, request: DefectAnalysisRequest):
    """对测试用例进行缺陷分析"""
    from app.database import get_db_connection
    from dm_agent import create_llm_client
    from dotenv import load_dotenv
    import os

    # 获取执行记录
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT te.*, tc.name as testcase_name, tc.description as testcase_description,
               tc.steps as testcase_steps, tc.expected_result as testcase_expected_result
        FROM test_executions te
        LEFT JOIN test_cases tc ON te.testcase_id = tc.id
        WHERE te.id = ? AND te.testcase_id = ?
    """, (request.execution_id, testcase_id))

    execution = cursor.fetchone()
    if not execution:
        conn.close()
        raise HTTPException(status_code=404, detail="执行记录不存在")

    # 获取执行步骤
    cursor.execute("SELECT steps_log FROM test_executions WHERE id = ?", (request.execution_id,))
    steps_row = cursor.fetchone()
    steps_log = []
    if steps_row and steps_row['steps_log']:
        try:
            steps_log = json.loads(steps_row['steps_log'])
        except:
            steps_log = []

    # 构建 Prompt
    steps_text = "\n".join([
        f"步骤{i+1}: {step.get('step_abbreviation', step.get('action', ''))}\n"
        f"  思考: {step.get('thought', '')}\n"
        f"  动作: {step.get('action', '')}\n"
        f"  观察: {step.get('observation', '')}\n"
        for i, step in enumerate(steps_log)
    ])

    prompt = f"""你是一个专业的测试工程师，请分析以下测试用例执行失败的原因：

【测试用例信息】
- 用例名称：{execution['testcase_name']}
- 用例描述：{execution.get('testcase_description', '')}
- 测试步骤：{execution.get('testcase_steps', '')}
- 预期结果：{execution.get('testcase_expected_result', '')}

【执行情况】
- 执行状态：{execution['status']}
- 执行耗时：{execution['duration'] or 0}秒
- 执行步骤数：{len(steps_log)}
- 最终判断：{execution.get('final_answer', '')}

【执行步骤详情】
{steps_text}

请按以下格式输出分析结果（使用Markdown格式）：

## 1. 失败原因分类
- [ ] 功能缺陷
- [ ] 环境问题
- [ ] 测试用例问题
- [ ] 网络问题
- [ ] 其他

## 2. 严重程度
- [ ] 严重（阻塞性问题）
- [ ] 一般（主要功能受影响）
- [ ] 轻微（次要功能或体验问题）

## 3. 根因分析
详细描述导致失败的根本原因

## 4. 建议的修复方案
提供具体的修复建议和验证方法

## 5. 相关建议
其他需要注意的问题或改进建议
"""

    # 调用 LLM
    try:
        load_dotenv()
        api_key = os.getenv("API_KEY")
        base_url = os.getenv("BASE_URL", "")

        if not api_key:
            raise HTTPException(status_code=500, detail="API key 未配置")

        client = create_llm_client(
            provider="qwen",
            api_key=api_key,
            model="qwen3.5-flash",
            base_url=base_url
        )

        response = client.complete(
            messages=[
                {"role": "system", "content": "你是一个专业的测试工程师，负责分析测试用例执行失败的原因。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )

        analysis_result = client.extract_text(response)

        # 保存分析结果到数据库
        cursor.execute("""
            INSERT INTO defect_analyses (testcase_id, execution_id, analysis_result)
            VALUES (?, ?, ?)
        """, (testcase_id, request.execution_id, analysis_result))

        conn.commit()
        analysis_id = cursor.lastrowid

        conn.close()

        return ApiResponse(data={
            "analysis_id": analysis_id,
            "analysis_result": analysis_result,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

    except Exception as e:
        conn.close()
        logger.error(f"缺陷分析失败：{e}")
        raise HTTPException(status_code=500, detail=f"缺陷分析失败：{str(e)}")


@api_router.get("/testcases/{testcase_id}/defect-analyses", response_model=ApiResponse)
async def get_defect_analyses(testcase_id: int):
    """获取测试用例的缺陷分析历史"""
    from app.database import get_db_connection

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, execution_id, analysis_result, created_at
        FROM defect_analyses
        WHERE testcase_id = ?
        ORDER BY created_at DESC
    """, (testcase_id,))

    rows = cursor.fetchall()
    analyses = []
    for row in rows:
        analyses.append({
            "id": row['id'],
            "execution_id": row['execution_id'],
            "analysis_result": row['analysis_result'],
            "created_at": row['created_at']
        })

    conn.close()

    return ApiResponse(data={"analyses": analyses})


@api_router.get("/logs/execution")
async def get_execution_logs():
    """获取执行日志"""
    try:
        logs = service_get_logs()
        return {"logs": logs}
    except Exception as e:
        logger.error(f"获取日志失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 脚本回放执行 ====================

@api_router.post("/scripts/execute")
async def execute_script(request: dict):
    """执行 Playwright 回放脚本"""

    script_path = request.get("script_path", "")
    if not script_path:
        raise HTTPException(status_code=400, detail="缺少 script_path 参数")

    # 将相对路径转换为绝对路径
    # 相对路径格式：/screenshots/<execution_id>/replay_xxx.js
    if script_path.startswith("/screenshots/"):
        abs_script_path = str(DATA_DIR) + script_path
    else:
        raise HTTPException(status_code=400, detail="无效的脚本路径")

    # 检查文件是否存在
    if not os.path.exists(abs_script_path):
        raise HTTPException(status_code=404, detail=f"脚本文件不存在：{script_path}")

    # 在后台线程中执行脚本，避免阻塞事件循环
    result_holder = {"status": "running", "output": "", "error": ""}

    def run_script():
        try:
            proc = subprocess.Popen(
                ["node", abs_script_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='replace',
                cwd=str(DATA_DIR),
            )
            stdout, stderr = proc.communicate(timeout=120)
            result_holder["status"] = "success" if proc.returncode == 0 else "failed"
            result_holder["output"] = stdout
            result_holder["error"] = stderr
            result_holder["exit_code"] = proc.returncode
        except subprocess.TimeoutExpired:
            proc.kill()
            result_holder["status"] = "timeout"
            result_holder["error"] = "脚本执行超时（120秒）"
        except FileNotFoundError:
            result_holder["status"] = "failed"
            result_holder["error"] = "未找到 node 命令，请确保已安装 Node.js"
        except Exception as e:
            result_holder["status"] = "failed"
            result_holder["error"] = str(e)

    thread = threading.Thread(target=run_script, daemon=True)
    thread.start()
    thread.join(timeout=130)  # 主线程最多等 130 秒

    if thread.is_alive():
        return {
            "status": "timeout",
            "output": "",
            "error": "脚本执行超时"
        }

    return {
        "status": result_holder["status"],
        "output": result_holder.get("output", ""),
        "error": result_holder.get("error", ""),
        "exit_code": result_holder.get("exit_code", -1)
    }


# ==================== 注册路由 ====================

app.include_router(api_router)

# 健康检查
@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "ok", "service": "AI自动化测试平台"}


# 初始化数据库
init_database()


def recover_pending_testcases():
    """
    重启时重置所有未完成状态的测试用例
    
    系统重启后，将所有"等待执行"和"执行中"的用例重置为"待测试"状态
    因为实际执行已经中断，需要重新执行
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # 重置"等待执行"状态的用例
    cursor.execute("""
        SELECT id, name FROM test_cases
        WHERE status = '等待执行'
    """)
    rows = cursor.fetchall()
    
    recovered_count = 0
    for row in rows:
        testcase_id = row['id']
        cursor.execute("""
            UPDATE test_cases
            SET status = '待测试'
            WHERE id = ?
        """, (testcase_id,))
        recovered_count += 1
        logger.info(f"[恢复] 重置测试用例：testcase_id={testcase_id}, name={row['name']} (等待执行 → 待测试)")

    # 重置"执行中"状态的用例
    cursor.execute("""
        SELECT id, name FROM test_cases
        WHERE status = '执行中'
    """)
    rows = cursor.fetchall()
    
    for row in rows:
        testcase_id = row['id']
        cursor.execute("""
            UPDATE test_cases
            SET status = '待测试'
            WHERE id = ?
        """, (testcase_id,))
        recovered_count += 1
        logger.info(f"[恢复] 重置测试用例：testcase_id={testcase_id}, name={row['name']} (执行中 → 待测试)")

    # 同时恢复 test_executions 表中 'running' 状态的记录
    cursor.execute("""
        SELECT id, testcase_id FROM test_executions
        WHERE status = 'running'
    """)
    rows = cursor.fetchall()
    for row in rows:
        cursor.execute("""
            UPDATE test_executions
            SET status = 'pending',
                error_message = '后端重启，任务中断',
                end_time = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (row['id'],))

    conn.commit()
    conn.close()

    if recovered_count > 0:
        logger.info(f"[恢复] 共重置 {recovered_count} 条中断的测试用例为「待测试」状态")
    else:
        logger.info("[恢复] 没有需要重置的测试用例")


# 生命周期事件处理器
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # ==================== 启动时 ====================
    logger.info("应用启动中...")

    # 1. 初始化 Agent 池（使用单例）
    pool = get_agent_pool()
    pool.initialize()
    logger.info("Agent 资源池已初始化")

    # 2. 恢复重启前的测试用例（将"等待执行"和"执行中"重置为"待测试"）
    recover_pending_testcases()

    # 3. 启动任务调度器
    scheduler = get_task_scheduler()
    await scheduler.start()

    # 在后台运行调度器
    asyncio.create_task(scheduler.run_loop(str(SCREENSHOT_DIR)))

    logger.info("任务调度器已启动")

    yield  # 应用运行中

    # ==================== 关闭时 ====================
    logger.info("应用关闭中...")

    scheduler = get_task_scheduler()
    await scheduler.stop()

    pool = get_agent_pool()
    pool.cleanup()

    logger.info("应用已关闭")


# ==================== 端口管理工具 ====================

def check_port(port: int) -> bool:
    """检查端口是否被占用"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            result = s.connect_ex(('127.0.0.1', port))
            return result == 0
    except:
        return False


def kill_process_on_port(port: int) -> bool:
    """终止占用指定端口的进程"""
    try:
        for conn in psutil.net_connections():
            if conn.laddr.port == port and conn.status == 'LISTEN':
                try:
                    process = psutil.Process(conn.pid)
                    logger.warning(f"发现端口 {port} 被进程 {process.name()} (PID: {conn.pid}) 占用")
                    process.terminate()
                    logger.info(f"已终止进程 {conn.pid}")
                    return True
                except psutil.NoSuchProcess:
                    logger.warning(f"进程 {conn.pid} 已不存在")
                except psutil.AccessDenied:
                    logger.error(f"无权限终止进程 {conn.pid}，请以管理员身份运行")
                    return False
        return False
    except Exception as e:
        logger.error(f"检查端口 {port} 时出错: {e}")
        return False


def setup_port(port: int):
    """设置端口，检查并终止占用进程"""
    if check_port(port):
        logger.warning(f"端口 {port} 已被占用，正在尝试释放...")
        if kill_process_on_port(port):
            import time
            time.sleep(2)  # 等待进程完全终止
            if not check_port(port):
                logger.info(f"端口 {port} 已成功释放")
            else:
                logger.error(f"端口 {port} 仍被占用，可能需要手动处理")
        else:
            logger.warning(f"未能自动释放端口 {port}")
    else:
        logger.info(f"端口 {port} 可用")


# 设置 lifespan
app.router.lifespan_context = lifespan


# 启动时恢复任务
recover_pending_testcases()


if __name__ == "__main__":
    import uvicorn
    
    # 检查并设置 8080 端口
    setup_port(8080)
    
    uvicorn.run(app, host="0.0.0.0", port=8080)

