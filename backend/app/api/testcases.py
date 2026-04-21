"""测试用例管理 API"""

import os
import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, UploadFile, File, HTTPException

from app.database import get_db_connection
from app.models import TestCaseCreate, BatchDeleteRequest, GenerateTestCasesRequest, ApiResponse
from app.services import TestCaseGenerator
from app.execution_service import logger

from app.api import api_router

# 数据目录
backend_dir = Path(__file__).parent.parent.parent
DATA_DIR = backend_dir / "data"
UPLOAD_DIR = DATA_DIR / "uploads" / "documents"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@api_router.post("/documents/{document_id}/generate-testcases", response_model=ApiResponse)
async def generate_testcases(document_id: int, request: GenerateTestCasesRequest):
    """AI 生成测试用例"""
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
        from dm_agent import create_llm_client
        client = create_llm_client(
            provider=request.provider,
            api_key=os.getenv("API_KEY"),
            model=request.model,
            base_url=os.getenv("BASE_URL", ""),
        )

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
        raise HTTPException(status_code=500, detail=f"生成测试用例失败：{str(e)}")


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
    file: UploadFile = File(..., description="Excel 文件")
):
    """从 Excel 导入测试用例"""
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="只支持 Excel 文件格式 (.xlsx, .xls)")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = UPLOAD_DIR / f"testcases_import_{project_id}_{timestamp}_{file.filename}"

    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    try:
        test_cases_data = ExcelParser.parse_test_cases(str(file_path))

        if not test_cases_data:
            raise HTTPException(status_code=400, detail="Excel 文件中没有找到有效的测试用例")

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
        raise HTTPException(status_code=500, detail=f"导入失败：{str(e)}")


@api_router.get("/testcases/export/template")
async def download_excel_template():
    """下载 Excel 导入模板"""
    from fastapi.responses import Response

    excel_data = ExcelParser.generate_excel_template()

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

    cursor.execute(f"SELECT COUNT(*) as total FROM test_cases WHERE {where_clause}", params)
    total = cursor.fetchone()["total"]

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
        try:
            case["steps"] = json.loads(case["steps"])
        except:
            if case["steps"]:
                case["steps"] = case["steps"].split('\n')
            else:
                case["steps"] = []
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
    try:
        case["steps"] = json.loads(case["steps"])
    except:
        if case["steps"]:
            case["steps"] = case["steps"].split('\n')
        else:
            case["steps"] = []
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

    cursor.execute("SELECT id FROM test_cases WHERE id = ?", (testcase_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="测试用例不存在")

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
