"""数据库更新辅助模块"""

import json
import logging
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Any

from app.database import get_db_connection

logger = logging.getLogger(__name__)


def update_testcase_status(
    testcase_id: int,
    exec_status: str,
    steps: List[Any],
    gif_path: Optional[str] = None,
    script_path: Optional[str] = None,
    final_answer: Optional[str] = None,
    error_message: Optional[str] = None,
    execution_id: Optional[str] = None,
    network_path: Optional[str] = None
):
    """更新测试用例状态到数据库

    使用快速提交策略，最小化数据库锁持有时间

    Args:
        testcase_id: 测试用例 ID
        exec_status: 执行状态
        steps: 执行步骤列表
        gif_path: GIF 文件路径
        script_path: 脚本文件路径
        final_answer: 最终答案
        error_message: 错误信息
        execution_id: 执行记录 ID
        network_path: 网络追踪文件路径
    """
    try:
        # 序列化 steps 为 JSON
        steps_json = json.dumps([asdict(step) for step in steps], ensure_ascii=False) if steps else "[]"

        # 将 GIF 路径转换为相对路径（用于前端访问）
        relative_gif_path = _convert_to_relative_path(gif_path, 'screenshots')
        relative_script_path = _convert_to_relative_path(script_path, 'screenshots')
        relative_network_path = _convert_to_relative_path(network_path, 'screenshots')

        # 获取当前日期
        today = datetime.now().strftime("%Y-%m-%d")

        # 计算耗时（独立查询，避免持有锁太久）
        duration = _calculate_duration(execution_id)

        # 使用事务快速更新
        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            # 先更新 test_cases 表（快速提交）
            cursor.execute("""
                UPDATE test_cases
                SET status = ?,
                    gif_path = ?,
                    script_path = ?,
                    network_path = ?,
                    tester = ?,
                    test_date = ?
                WHERE id = ?
            """, (exec_status, relative_gif_path, relative_script_path, relative_network_path, "AI", today, testcase_id))
            conn.commit()  # 立即提交 test_cases 更新

            # 然后更新 test_executions 表
            if execution_id:
                cursor.execute("""
                    UPDATE test_executions
                    SET status = ?,
                        result = ?,
                        gif_path = ?,
                        script_path = ?,
                        network_path = ?,
                        error_message = ?,
                        steps_log = ?,
                        end_time = CURRENT_TIMESTAMP,
                        duration = ?,
                        final_answer = ?
                    WHERE id = ?
                """, (
                    'completed' if exec_status in ['执行通过', '执行不通过'] else 'failed',
                    'passed' if exec_status == '执行通过' else 'failed',
                    relative_gif_path,
                    relative_script_path,
                    relative_network_path,
                    error_message,
                    steps_json,
                    duration,
                    final_answer,
                    execution_id
                ))
            else:
                # 如果没有 execution_id，更新最新的一条
                cursor.execute("""
                    UPDATE test_executions
                    SET status = ?,
                        result = ?,
                        gif_path = ?,
                        script_path = ?,
                        error_message = ?,
                        steps_log = ?,
                        end_time = CURRENT_TIMESTAMP,
                        duration = ?,
                        final_answer = ?
                    WHERE testcase_id = ?
                    ORDER BY start_time DESC
                    LIMIT 1
                """, (
                    'completed' if exec_status in ['执行通过', '执行不通过'] else 'failed',
                    'passed' if exec_status == '执行通过' else 'failed',
                    relative_gif_path,
                    relative_script_path,
                    error_message,
                    steps_json,
                    duration,
                    final_answer,
                    testcase_id
                ))
            conn.commit()  # 提交 test_executions 更新

        except Exception as e:
            conn.rollback()
            raise
        finally:
            conn.close()

        logger.info(f"[DB] 测试用例状态已更新：testcase_id={testcase_id}, execution_id={execution_id}, status={exec_status}")

    except Exception as e:
        logger.error(f"[DB] 更新测试用例状态失败：{e}")


def _convert_to_relative_path(file_path: Optional[str], base_dir: str) -> Optional[str]:
    """将绝对路径转换为相对路径

    Args:
        file_path: 绝对路径
        base_dir: 基础目录名

    Returns:
        相对路径
    """
    if not file_path:
        return None

    path_obj = Path(file_path)
    try:
        base_idx = path_obj.parts.index(base_dir)
        relative_parts = path_obj.parts[base_idx:]
        relative_path = '/' + '/'.join(relative_parts).replace('\\', '/')
        return relative_path
    except (ValueError, IndexError):
        return str(file_path).replace('\\', '/')


def _calculate_duration(execution_id: Optional[str]) -> Optional[int]:
    """计算执行耗时（独立查询，不持有锁）

    Args:
        execution_id: 执行记录 ID

    Returns:
        耗时（秒），失败返回 None
    """
    if not execution_id:
        return None

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT start_time FROM test_executions WHERE id = ?", (execution_id,))
        row = cursor.fetchone()
        conn.close()

        if row and row['start_time']:
            start_str = str(row['start_time'])
            if 'T' in start_str:
                start_str = start_str.replace('T', ' ').replace('Z', '')
            if '.' in start_str:
                start_str = start_str.split('.')[0]
            start = datetime.strptime(start_str, '%Y-%m-%d %H:%M:%S')
            duration = int((datetime.utcnow() - start).total_seconds())
            return duration
    except Exception as e:
        logger.warning(f"[DB] 计算耗时失败：{e}")

    return None
