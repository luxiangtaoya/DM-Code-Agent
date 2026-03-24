# AI 自动化测试平台

<div align="center">

基于 AI Agent 的智能化测试用例生成与执行平台

[![Vue](https://img.shields.io/badge/Vue-2.7-brightgreen.svg)](https://vuejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-blue.svg)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3.7+-blue.svg)](https://www.python.org/)

</div>

## 项目简介

AI 自动化测试平台是一个基于 ReAct Agent 架构的智能测试平台，能够：

- 📄 **解析需求文档** - 自动解析 PDF/Word 文档，提取测试需求
- 🤖 **AI 生成用例** - 基于需求自动生成测试用例
- 🧪 **智能执行测试** - Agent 自动执行测试步骤并生成截图
- 📊 **测试报告分析** - 可视化测试结果，AI 分析缺陷原因

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Vue 2.7 + Element UI + ECharts + Vue Router + Vuex |
| 后端 | Python FastAPI + SQLite + Uvicorn |
| AI | 多 LLM 支持 (DeepSeek/Qwen/Claude/OpenAI) |
| Agent | ReAct 架构 + MCP 协议 + Skill 系统 |

## 功能特性

### 项目管理
- 创建/编辑/删除测试项目
- 项目级别的测试用例和执行记录管理

### 文档管理
- 上传需求文档 (PDF/Word)
- 自动提取文档文本内容

### 测试用例
- AI 自动生成测试用例
- 手动创建/编辑测试用例
- Excel 批量导入/导出
- 支持优先级、类型、状态管理

### 测试执行
- Agent 自动执行测试步骤
- 实时查看执行进度 (WebSocket)
- 自动生成执行截图 (GIF)
- 执行历史记录

### 报告分析
- 测试统计数据可视化
- 执行时间分布
- 缺陷 AI 智能分析

## 快速开始

### 环境要求

- Python 3.7+
- Node.js 14+
- LLM API Key (推荐 DeepSeek/Qwen)

### 安装依赖

```bash
# 后端依赖
cd backend
pip install -r requirements.txt

# 前端依赖
cd ../frontend
npm install
```

### 配置环境变量

复制 `backend/.env.example` 为 `backend/.env`：

```bash
cd backend
cp .env.example .env
```

编辑 `.env` 文件：

```env
# LLM API 配置
API_KEY=your_api_key_here
BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

# 或使用其他提供商
# DEEPSEEK_API_KEY=sk-xxx
# OPENAI_API_KEY=sk-xxx
```

### 启动服务

```bash
# 启动后端 (端口 8080)
cd backend
python -m app.main

# 启动前端 (端口 8081)
cd frontend
npm run serve
```

访问: http://localhost:8081

## 目录结构

```
DM-Code-Agent/
├── backend/                    # 后端服务
│   ├── app/                   # FastAPI 应用
│   │   ├── main.py           # 主入口
│   │   ├── database.py       # 数据库
│   │   ├── models.py         # 数据模型
│   │   ├── execution_service.py  # 执行服务
│   │   └── services/         # 业务服务
│   ├── dm_agent/             # Agent 核心包
│   │   ├── core/             # ReAct Agent
│   │   ├── clients/          # LLM 客户端
│   │   ├── tools/            # 工具集
│   │   ├── skills/           # 技能系统
│   │   ├── mcp/              # MCP 协议
│   │   └── screenshot/       # 截图管理
│   ├── data/                 # 数据目录
│   └── requirements.txt      # Python 依赖
├── frontend/                  # 前端应用
│   ├── src/
│   │   ├── views/            # 页面组件
│   │   ├── api/              # API 封装
│   │   ├── router/           # 路由配置
│   │   └── store/            # Vuex 状态
│   └── package.json          # 依赖配置
├── docs/                      # 文档
└── README.md                  # 本文件
```

## API 文档

后端启动后访问: http://localhost:8080/docs

## 开发说明

### 前端开发

```bash
cd frontend
npm run serve    # 开发模式 (端口 8081)
npm run build    # 生产构建
```

### 后端开发

```bash
cd backend
python -m app.main    # 启动服务 (端口 8080)
```

## 常见问题

### 1. 后端启动失败

- 检查 Python 版本 >= 3.7
- 确保已安装所有依赖 `pip install -r requirements.txt`
- 检查端口 8080 是否被占用

### 2. 前端无法连接后端

- 确认后端已启动在 http://localhost:8080
- 检查 `frontend/.env.development` 配置

### 3. Agent 执行失败

- 检查 `.env` 中的 API_KEY 是否正确
- 确认 BASE_URL 可访问
- 查看后端日志获取详细错误信息

## License

MIT License

## 作者

[luxiangtaoya](https://github.com/luxiangtaoya)
