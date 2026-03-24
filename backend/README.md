# DM-Code-Agent Backend

后端服务模块，提供 FastAPI REST API 和 AI Agent 执行引擎。

## 目录结构

```
backend/
├── app/                       # FastAPI Web 应用
│   ├── main.py              # 主入口 (端口 8080)
│   ├── database.py          # SQLite 数据库
│   ├── models.py            # Pydantic 数据模型
│   ├── execution_service.py # 测试执行调度服务
│   └── services/            # 业务服务
│       ├── document_parser.py   # 文档解析
│       ├── testcase_generator.py # 测试用例生成
│       └── excel_parser.py      # Excel 导入导出
│
├── dm_agent/                 # AI Agent 核心引擎
│   ├── core/                # ReAct Agent 实现
│   ├── clients/             # LLM 客户端 (多模型支持)
│   ├── tools/               # 工具集
│   ├── skills/              # 专家技能系统
│   ├── mcp/                 # MCP 协议支持
│   ├── screenshot/          # 截图管理
│   └── logger.py            # 日志配置
│
├── data/                     # 数据目录
│   ├── testing_platform.db  # SQLite 数据库
│   ├── uploads/             # 上传文件
│   └── screenshots/         # 执行截图
│
└── requirements.txt          # Python 依赖
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env`：

```bash
cp .env.example .env
```

编辑 `.env`：

```env
# LLM API 配置
API_KEY=your_api_key_here
BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
```

### 3. 启动服务

```bash
python -m app.main
```

服务将启动在: http://localhost:8080

API 文档: http://localhost:8080/docs

## DM Agent 核心包

### 多 LLM 支持

- DeepSeek
- Qwen (通义千问)
- OpenAI (GPT-3.5/GPT-4)
- Claude (Anthropic)
- Gemini (Google)

### 工具能力

- **文件操作**: 读取、创建、编辑文件
- **代码分析**: AST 解析、函数签名提取
- **测试执行**: 运行测试、代码检查
- **Shell 命令**: 执行系统命令
- **浏览器**: MCP Playwright 集成

### Skill 技能系统

自动激活领域专家能力：
- Python 专家
- 数据库专家
- 前端开发专家

## API 端点

### 项目管理
- `GET /api/v1/projects` - 获取项目列表
- `POST /api/v1/projects` - 创建项目
- `PUT /api/v1/projects/{id}` - 更新项目
- `DELETE /api/v1/projects/{id}` - 删除项目

### 文档管理
- `POST /api/v1/projects/{id}/documents` - 上传文档
- `GET /api/v1/projects/{id}/documents` - 获取文档列表

### 测试用例
- `GET /api/v1/projects/{id}/testcases` - 获取用例列表
- `POST /api/v1/projects/{id}/testcases` - 创建用例
- `POST /api/v1/projects/{id}/testcases/batch` - 批量创建
- `POST /api/v1/projects/{id}/testcases/import/excel` - Excel 导入
- `POST /api/v1/testcases/batch-execute` - 批量执行

### 执行记录
- `GET /api/v1/projects/{id}/executions` - 获取执行记录
- `GET /api/v1/executions/{id}` - 获取执行详情
- `WS /api/v1/ws/executions/{id}` - WebSocket 实时推送

### 报告分析
- `GET /api/v1/projects/{id}/reports/statistics` - 获取统计数据
- `POST /api/v1/testcases/{id}/analyze-defect` - AI 缺陷分析

## 开发说明

### 数据库初始化

首次启动会自动创建 `data/testing_platform.db` 及所需表结构。

### 日志配置

日志文件位于 `logs/` 目录。

### MCP 配置

编辑 `mcp_config.json` 添加 MCP 工具支持。

## License

MIT License
