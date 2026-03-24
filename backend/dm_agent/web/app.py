"""FastAPI Web 应用 - 提供 Web 界面和实时任务执行"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from queue import Queue
from threading import Thread

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .. import ReactAgent, create_llm_client, default_tools
from ..mcp import MCPManager, load_mcp_config
from ..screenshot import ScreenshotManager


app = FastAPI(title="DM Code Agent Web Interface")


# 全局更新队列 - 用于跨线程通信
update_queues: Dict[str, Queue] = {}


@dataclass
class TaskStep:
    """任务步骤信息"""
    step_num: int
    thought: str
    step_abbreviation: str
    action: str
    observation: str
    timestamp: str


@dataclass
class TaskStatus:
    """任务状态"""
    task_id: str
    task: str
    status: str  # "running", "completed", "failed"
    current_step: int
    total_steps: int
    steps: List[TaskStep]
    gif_path: Optional[str] = None
    error_message: Optional[str] = None
    final_answer: Optional[str] = None


class TaskRequest(BaseModel):
    """任务请求"""
    task: str
    provider: str = "qwen"
    model: str = "qwen3.5-flash"
    api_key: Optional[str] = None
    base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    max_steps: int = 100
    temperature: float = 0.7
    enable_screenshots: bool = True


# 全局状态
active_tasks: Dict[str, TaskStatus] = {}
connected_websockets: Dict[str, List[WebSocket]] = {}


class ConnectionManager:
    """WebSocket 连接管理器"""

    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, task_id: str):
        """连接 WebSocket"""
        await websocket.accept()
        if task_id not in self.active_connections:
            self.active_connections[task_id] = []
        self.active_connections[task_id].append(websocket)

    def disconnect(self, websocket: WebSocket, task_id: str):
        """断开连接"""
        if task_id in self.active_connections:
            self.active_connections[task_id].remove(websocket)
            if not self.active_connections[task_id]:
                del self.active_connections[task_id]

    async def send_update(self, task_id: str, message: dict):
        """发送更新到所有连接的客户端"""
        if task_id in self.active_connections:
            disconnected = []
            for connection in self.active_connections[task_id]:
                try:
                    await connection.send_json(message)
                except:
                    disconnected.append(connection)

            for connection in disconnected:
                self.disconnect(connection, task_id)


manager = ConnectionManager()


@app.get("/", response_class=HTMLResponse)
async def read_root():
    """返回前端页面"""
    html_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>DM Code Agent</h1><p>Web interface not found</p>"


@app.post("/api/tasks")
async def create_task(request: TaskRequest, background_tasks: BackgroundTasks):
    """创建并启动新任务"""
    import uuid
    task_id = str(uuid.uuid4())

    # 获取 API key
    api_key = request.api_key or os.getenv("API_KEY")
    if not api_key:
        raise HTTPException(status_code=400, detail="API key is required")

    # 创建任务状态
    task_status = TaskStatus(
        task_id=task_id,
        task=request.task,
        status="running",
        current_step=0,
        total_steps=request.max_steps,
        steps=[]
    )
    active_tasks[task_id] = task_status

    # 在后台执行任务
    background_tasks.add_task(
        execute_task,
        task_id,
        request
    )

    return {"task_id": task_id, "status": "running"}


@app.get("/api/tasks/{task_id}")
async def get_task_status(task_id: str):
    """获取任务状态"""
    if task_id not in active_tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    status = active_tasks[task_id]
    return asdict(status)


@app.get("/api/tasks/{task_id}/gif")
async def get_task_gif(task_id: str):
    """获取任务生成的 GIF"""
    if task_id not in active_tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    status = active_tasks[task_id]
    if not status.gif_path or not os.path.exists(status.gif_path):
        raise HTTPException(status_code=404, detail="GIF not available")

    return FileResponse(
        status.gif_path,
        media_type="image/gif",
        filename=f"{task_id}.gif"
    )


@app.websocket("/ws/{task_id}")
async def websocket_endpoint(websocket: WebSocket, task_id: str):
    """WebSocket 端点 - 实时更新"""
    await manager.connect(websocket, task_id)

    try:
        # 发送初始状态
        if task_id in active_tasks:
            await manager.send_update(task_id, {
                "type": "status_update",
                "data": asdict(active_tasks[task_id])
            })

        # 保持连接
        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        manager.disconnect(websocket, task_id)


def run_agent_in_thread(
    task_id: str,
    request: TaskRequest,
    update_queue: Queue,
    active_tasks: Dict[str, TaskStatus]
):
    """在独立线程中运行 Agent（同步）"""
    try:
        # 初始化 MCP
        mcp_config = load_mcp_config()
        mcp_manager = MCPManager(mcp_config)

        try:
            started_count = mcp_manager.start_all()
            update_queue.put({
                "type": "mcp_started",
                "data": {
                    "servers_started": started_count,
                    "message": f"已启动 {started_count} 个 MCP 服务器"
                }
            })

            # 获取工具
            mcp_tools = mcp_manager.get_tools()
            tools = default_tools(include_mcp=True, mcp_tools=mcp_tools)

            client = create_llm_client(
                provider=request.provider,
                api_key=request.api_key or os.getenv("API_KEY"),
                model=request.model,
                base_url=request.base_url,
            )

            # 创建截图管理器
            screenshot_manager = None
            if request.enable_screenshots:
                screenshot_manager = ScreenshotManager(
                    output_dir="task_screenshots",
                    enable_gif=True,
                    gif_duration=1000
                )
                screenshot_manager.start_task(task_id)
                print(f"✓ 截图管理器已初始化")

            # 创建步骤回调函数
            def step_callback(step_num: int, step: Any) -> None:
                print(f"[步骤 {step_num}] {step.step_abbreviation} - {step.action}")
                
                step_info = TaskStep(
                    step_num=step_num,
                    thought=step.thought,
                    step_abbreviation=step.step_abbreviation,
                    action=step.action,
                    observation=step.observation,
                    timestamp=datetime.now().isoformat()
                )

                # 更新任务状态
                if task_id in active_tasks:
                    active_tasks[task_id].steps.append(step_info)
                    active_tasks[task_id].current_step = step_num

                # 将更新放入队列
                update_queue.put({
                    "type": "step_update",
                    "data": asdict(step_info)
                })
                print(f"✓ 已将步骤 {step_num} 放入更新队列")

                # 截图逻辑
                if screenshot_manager and mcp_manager:
                    try:
                        playwright_client = mcp_manager.clients.get("playwright")
                        if playwright_client and playwright_client.is_running():
                            print(f"📸 正在截图...")
                            
                            # 调用 Playwright MCP 的截图工具（正确的工具名称）
                            screenshot_result = playwright_client.call_tool("browser_take_screenshot", {})
                            
                            if screenshot_result:
                                print(f"✓ 截图工具返回: {type(screenshot_result)}, 长度: {len(str(screenshot_result))}")
                                
                                # 解析 Playwright MCP 返回的文件路径
                                import re
                                import base64
                                
                                # 提取文件路径：[Screenshot of viewport](C:\path\to\file.png)
                                path_match = re.search(r'\[Screenshot[^\]]*\]\(([^\)]+)\)', str(screenshot_result))
                                
                                if path_match:
                                    screenshot_path = path_match.group(1)
                                    print(f"✓ 提取到截图路径: {screenshot_path}")
                                    
                                    # 读取图片文件并转换为 base64
                                    try:
                                        with open(screenshot_path, 'rb') as f:
                                            image_data = f.read()
                                        
                                        base64_data = base64.b64encode(image_data).decode('utf-8')
                                        print(f"✓ 转换为 base64, 长度: {len(base64_data)}")
                                        
                                        # 保存截图（带步骤标注）
                                        saved_path = screenshot_manager.add_screenshot_from_base64(
                                            step.step_abbreviation,
                                            base64_data
                                        )
                                        print(f"✓ 已保存截图: {saved_path}")
                                        print(f"✓ 当前截图数量: {screenshot_manager.get_screenshot_count()}")
                                        
                                    except FileNotFoundError:
                                        print(f"⚠️ 截图文件不存在: {screenshot_path}")
                                    except Exception as e:
                                        print(f"❌ 读取截图文件失败: {e}")
                                else:
                                    print(f"⚠️ 无法从结果中提取截图路径")
                                    print(f"⚠️ 截图结果前200字符: {str(screenshot_result)[:200]}")
                            else:
                                print(f"⚠️ 截图结果为空")
                    except Exception as e:
                        print(f"❌ 截图失败: {e}")
                        import traceback
                        traceback.print_exc()

            agent = ReactAgent(
                client,
                tools,
                max_steps=request.max_steps,
                temperature=request.temperature,
                step_callback=step_callback,
                enable_planning=False,
                enable_compression=True
            )

            # 执行任务
            result = agent.run(request.task)

            # 生成 GIF
            gif_path = None
            if screenshot_manager:
                gif_path = screenshot_manager.finish_task()
                print(f"✓ GIF 已生成: {gif_path}")

            # 发送完成通知
            update_queue.put({
                "type": "task_completed",
                "data": {
                    "final_answer": result.get("final_answer", ""),
                    "gif_path": gif_path
                }
            })

        finally:
            mcp_manager.stop_all()

    except Exception as e:
        import traceback
        traceback.print_exc()
        update_queue.put({
            "type": "task_failed",
            "data": {
                "error_message": str(e)
            }
        })


async def execute_task(task_id: str, request: TaskRequest):
    """在后台执行任务（异步协调器）"""
    try:
        # 创建更新队列
        update_queue = Queue()
        update_queues[task_id] = update_queue

        # 发送初始状态
        await manager.send_update(task_id, {
            "type": "task_started",
            "data": {
                "task_id": task_id,
                "task": request.task,
                "status": "running",
                "message": "任务已启动，正在初始化..."
            }
        })

        # 在独立线程中启动 Agent
        thread = Thread(
            target=run_agent_in_thread,
            args=(task_id, request, update_queue, active_tasks),
            daemon=True
        )
        thread.start()

        # 持续从队列读取更新并发送到 WebSocket
        while True:
            try:
                # 非阻塞获取，超时 0.1 秒
                update = update_queue.get(timeout=0.1)
                
                # 更新任务状态
                if update["type"] == "step_update":
                    pass  # 步骤已在 active_tasks 中更新
                elif update["type"] == "task_completed":
                    if task_id in active_tasks:
                        active_tasks[task_id].status = "completed"
                        active_tasks[task_id].final_answer = update["data"]["final_answer"]
                        active_tasks[task_id].gif_path = update["data"]["gif_path"]
                elif update["type"] == "task_failed":
                    if task_id in active_tasks:
                        active_tasks[task_id].status = "failed"
                        active_tasks[task_id].error_message = update["data"]["error_message"]

                # 发送到 WebSocket
                await manager.send_update(task_id, update)
                print(f"✓ 已发送 {update['type']} 更新到 WebSocket")

                # 检查是否完成
                if update["type"] in ["task_completed", "task_failed"]:
                    break

            except:
                # 队列为空，检查线程是否还在运行
                if not thread.is_alive():
                    break
                await asyncio.sleep(0.05)

    except Exception as e:
        import traceback
        traceback.print_exc()
        if task_id in active_tasks:
            active_tasks[task_id].status = "failed"
            active_tasks[task_id].error_message = str(e)
            await manager.send_update(task_id, {
                "type": "task_failed",
                "data": asdict(active_tasks[task_id])
            })
    finally:
        # 清理队列
        if task_id in update_queues:
            del update_queues[task_id]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
