"""文档管理 API"""

import os
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form, HTTPException

from app.database import get_db_connection
from app.models import ApiResponse
from app.services.excel_parser import ExcelParser
from app.execution_service import logger

from app.api import api_router

# 数据目录
backend_dir = Path(__file__).parent.parent.parent
DATA_DIR = backend_dir / "data"
UPLOAD_DIR = DATA_DIR / "uploads" / "documents"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def extract_text_from_file(file_path: str) -> str:
    """从文件中提取文本"""
    from app.services import DocumentParser
    parser = DocumentParser()
    return parser.extract_text(file_path)


@api_router.post("/projects/{project_id}/documents", response_model=ApiResponse)
async def upload_document(
    project_id: int,
    file: UploadFile = File(...),
    title: Optional[str] = Form(None)
):
    """上传需求文档"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM projects WHERE id = ?", (project_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="项目不存在")

    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in [".pdf", ".docx", ".doc"]:
        conn.close()
        raise HTTPException(status_code=400, detail="不支持的文件格式")

    project_dir = UPLOAD_DIR / str(project_id)
    project_dir.mkdir(exist_ok=True)

    file_id = str(uuid.uuid4())
    file_path = project_dir / f"{file_id}{file_ext}"

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    try:
        extracted_text = extract_text_from_file(str(file_path))
    except Exception as e:
        os.remove(file_path)
        conn.close()
        raise HTTPException(status_code=400, detail=f"文档解析失败：{str(e)}")

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
