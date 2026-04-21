"""统计报告 API"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException

from app.database import get_db_connection
from app.models import DefectAnalysisRequest, StatisticsResponse, ApiResponse
from app.execution_service import logger

from app.api import api_router


@api_router.get("/projects/{project_id}/reports/statistics", response_model=ApiResponse)
async def get_project_statistics(
    project_id: int,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    status: Optional[str] = None
):
    """获取项目统计数据"""
    conn = get_db_connection()
    cursor = conn.cursor()

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

    status_stats = {
        "labels": ["执行通过", "执行不通过", "执行错误"],
        "data": [passed, failed, error]
    }

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

    step_ranges = {
        "1-3 步": 0,
        "4-6 步": 0,
        "7-10 步": 0,
        "11-15 步": 0,
        "16-20 步": 0,
        "21-30 步": 0,
        "30 步+": 0
    }

    for row in rows:
        cursor.execute("SELECT steps_log FROM test_executions WHERE id = ?", (row['execution_id'],))
        steps_row = cursor.fetchone()
        if steps_row and steps_row['steps_log']:
            try:
                steps = json.loads(steps_row['steps_log'])
                step_count = len(steps)
                if step_count <= 3:
                    step_ranges["1-3 步"] += 1
                elif step_count <= 6:
                    step_ranges["4-6 步"] += 1
                elif step_count <= 10:
                    step_ranges["7-10 步"] += 1
                elif step_count <= 15:
                    step_ranges["11-15 步"] += 1
                elif step_count <= 20:
                    step_ranges["16-20 步"] += 1
                elif step_count <= 30:
                    step_ranges["21-30 步"] += 1
                else:
                    step_ranges["30 步+"] += 1
            except:
                pass

    step_count_stats = step_ranges

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

    defects = []
    for row in rows:
        if (row['status'] == 'completed' and row['result'] == 'failed') or row['status'] == 'failed':
            cursor.execute(
                "SELECT COUNT(*) as count FROM defect_analyses WHERE testcase_id = ?",
                (row['testcase_id'],)
            )
            analysis_count_row = cursor.fetchone()
            analysis_count = analysis_count_row['count'] if analysis_count_row else 0

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

    cursor.execute("SELECT steps_log FROM test_executions WHERE id = ?", (request.execution_id,))
    steps_row = cursor.fetchone()
    steps_log = []
    if steps_row and steps_row['steps_log']:
        try:
            steps_log = json.loads(steps_row['steps_log'])
        except:
            steps_log = []

    steps_text = "\n".join([
        f"步骤{i+1}: {step.get('step_abbreviation', step.get('action', ''))}\n"
        f"  思考：{step.get('thought', '')}\n"
        f"  动作：{step.get('action', '')}\n"
        f"  观察：{step.get('observation', '')}\n"
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

请按以下格式输出分析结果（使用 Markdown 格式）：

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

    try:
        from dm_agent import create_llm_client
        from dotenv import load_dotenv
        import os

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
