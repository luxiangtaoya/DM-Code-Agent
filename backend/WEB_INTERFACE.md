# Web 界面使用指南

DM Code Agent 现在提供了友好的 Web 界面，支持实时监控任务执行、查看步骤进度，并自动生成浏览器自动化任务的截图动画。

## 功能特性

### 1. 实时任务执行监控
- 通过 WebSocket 实时推送任务执行进度
- 显示每个步骤的思考过程、操作和结果
- 进度条可视化当前执行进度

### 2. 浏览器自动化截图
- 自动为每个浏览器操作步骤截图
- 在截图上标注当前步骤名称
- 任务完成后自动生成 GIF 动画

### 3. 友好的 Web 界面
- 简洁直观的任务输入界面
- 支持多种 LLM 提供商
- 实时步骤列表和执行日志

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

新增依赖：
- `fastapi` - Web 框架
- `uvicorn` - ASGI 服务器
- `pydantic` - 数据验证
- `pillow` - 图片处理（用于截图和 GIF 生成）

### 2. 配置环境变量

在 `.env` 文件中配置你的 API Key：

```env
API_KEY=your_api_key_here
MODEL_NAME=qwen3.5-flash
BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
```

### 3. 启动 Web 服务器

```bash
python web_server.py
```

服务器将在 `http://localhost:8000` 启动。

### 4. 访问 Web 界面

打开浏览器访问：
- **主页**: http://localhost:8000
- **API 文档**: http://localhost:8000/docs

## 使用方法

### 通过 Web 界面执行任务

1. **输入任务描述**

在主页的任务输入框中输入你的任务，例如：
```
打开 https://example.com 并截图
```

2. **配置高级选项（可选）**

点击"高级配置"展开更多选项：
- 模型提供商（Qwen、OpenAI、DeepSeek、Claude）
- 模型名称
- API Key（留空使用环境变量）
- Base URL
- 最大步骤数
- 是否启用截图

3. **开始执行**

点击"开始执行"按钮，系统将：
- 创建任务并分配唯一 ID
- 建立 WebSocket 连接
- 实时推送执行进度
- 自动截图（如果启用）

4. **查看执行过程**

在执行过程中，你可以看到：
- 进度条显示当前进度
- 每个步骤的详细信息：
  - 步骤编号
  - 操作类型（如 `mcp_playwright_navigate`）
  - 步骤简述
  - 思考过程
  - 执行结果

5. **查看结果**

任务完成后：
- 显示最终答案
- 提供 GIF 动画（如果启用截图）
- 可以下载查看完整的执行过程

### API 使用

如果你更喜欢编程方式，也可以直接调用 API：

#### 创建任务

```bash
curl -X POST "http://localhost:8000/api/tasks" \
  -H "Content-Type: application/json" \
  -d '{
    "task": "打开 https://example.com 并截图",
    "provider": "qwen",
    "model": "qwen3.5-flash",
    "enable_screenshots": true
  }'
```

响应：
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "running"
}
```

#### 查询任务状态

```bash
curl "http://localhost:8000/api/tasks/{task_id}"
```

响应：
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "task": "打开 https://example.com 并截图",
  "status": "completed",
  "current_step": 3,
  "total_steps": 100,
  "steps": [...],
  "gif_path": "task_screenshots/20240101_120000/task_animation.gif",
  "final_answer": "任务完成"
}
```

#### 下载 GIF

```bash
curl "http://localhost:8000/api/tasks/{task_id}/gif" -o task.gif
```

#### WebSocket 实时更新

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/{task_id}');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  switch (data.type) {
    case 'status_update':
      console.log('状态更新:', data.data);
      break;
    case 'step_update':
      console.log('步骤更新:', data.data);
      break;
    case 'task_completed':
      console.log('任务完成:', data.data);
      break;
    case 'task_failed':
      console.log('任务失败:', data.data);
      break;
  }
};
```

## 截图功能说明

### 自动截图

当任务执行涉及浏览器操作（使用 Playwright MCP）时，系统会自动：
1. 在每个浏览器操作后截图
2. 在截图上添加步骤名称标注
3. 保存为 PNG 文件
4. 任务完成后生成 GIF 动画

### 截图存储

截图保存在 `task_screenshots/` 目录下：
```
task_screenshots/
├── {task_id}/
│   ├── 20240101_120000_step1.png
│   ├── 20240101_120001_step2.png
│   ├── 20240101_120002_step3.png
│   └── task_animation.gif
```

### 截图标注

每个截图都会在右上角添加步骤名称标注：
- 黑色半透明背景
- 白色文字
- 自动调整字体大小

### GIF 动画

- 帧间间隔：1000ms（可配置）
- 循环播放
- 包含所有步骤截图

## 示例任务

### 示例 1：简单网页访问

```
打开 https://www.baidu.com 并截图
```

执行步骤：
1. 导航到百度首页
2. 截取页面
3. 完成

### 示例 2：表单填写

```
打开登录页面，输入用户名和密码，然后点击登录按钮
```

执行步骤：
1. 导航到登录页面
2. 截图
3. 填写用户名
4. 截图
5. 填写密码
6. 截图
7. 点击登录按钮
8. 截图
9. 完成

### 示例 3：数据提取

```
打开新闻网站，提取前5条新闻标题
```

执行步骤：
1. 导航到新闻网站
2. 截图
3. 执行 JavaScript 提取标题
4. 显示结果
5. 完成

## 配置选项

### 服务器配置

在 `web_server.py` 中可以修改：
- 监听地址（默认 `0.0.0.0`）
- 端口（默认 `8000`）
- 自动重载（默认 `true`）

### 截图配置

在 `app.py` 的 `execute_task` 函数中：
```python
screenshot_manager = ScreenshotManager(
    output_dir="task_screenshots",
    enable_gif=True,
    gif_duration=1000  # GIF 每帧显示时间（毫秒）
)
```

## 故障排除

### 问题 1：无法启动服务器

**错误**: `ModuleNotFoundError: No module named 'fastapi'`

**解决**:
```bash
pip install -r requirements.txt
```

### 问题 2：无法生成 GIF

**错误**: `警告: 未安装 PIL/Pillow 库`

**解决**:
```bash
pip install pillow
```

### 问题 3：截图功能不工作

**可能原因**:
1. Playwright MCP 未启动
2. 任务未使用浏览器操作
3. 截图功能未启用

**解决**:
1. 确保 `mcp_config.json` 中启用了 Playwright
2. 在任务描述中明确要求浏览器操作
3. 在高级配置中启用"启用截图"

### 问题 4：WebSocket 连接失败

**可能原因**:
- 防火墙阻止连接
- 代理设置问题

**解决**:
1. 检查防火墙设置
2. 配置代理环境变量

## 技术架构

### 后端
- **FastAPI**: Web 框架
- **WebSocket**: 实时通信
- **BackgroundTasks**: 异步任务执行
- **Pillow**: 图片处理

### 前端
- **Vue.js 3**: 响应式 UI
- **Axios**: HTTP 请求
- **WebSocket API**: 实时更新

### 截图管理
- **ScreenshotManager**: 截图管理器
- **Playwright MCP**: 浏览器自动化
- **Pillow**: 图片标注和 GIF 生成

## 开发说明

### 添加新的 API 端点

在 `dm_agent/web/app.py` 中添加：

```python
@app.get("/api/custom")
async def custom_endpoint():
    return {"message": "Hello"}
```

### 修改前端界面

编辑 `dm_agent/web/static/index.html`，使用 Vue.js 组件系统。

### 扩展截图功能

修改 `dm_agent/screenshot/screenshot_manager.py` 的 `ScreenshotManager` 类。

## 许可证

本项目与 DM-Code-Agent 保持相同的许可证。
