# AI自动化测试平台 API接口文档

> 最后更新：2024-03-09

## 基础信息
- **基础路径**: `/api/v1`
- **数据格式**: `application/json`
- **认证方式**: 暂无（单用户模式）
- **WebSocket**: `/api/v1/ws/executions/{execution_id}`

---

## 1. 项目管理 API

### 1.1 获取项目列表
```
GET /api/v1/projects
```

**响应示例:**
```json
{
  "code": 0,
  "message": "success",
  "data": [
    {
      "id": 1,
      "name": "电商项目",
      "description": "用户模块功能测试",
      "status": "active",
      "created_at": "2024-03-09T12:00:00Z",
      "updated_at": "2024-03-09T12:00:00Z",
      "test_case_count": 15,
      "execution_count": 45
    }
  ]
}
```

### 1.2 创建项目
```
POST /api/v1/projects
```

**请求参数:**
```json
{
  "name": "项目名称",
  "description": "项目描述"
}
```

### 1.3 更新项目
```
PUT /api/v1/projects/{project_id}
```

### 1.4 删除项目
```
DELETE /api/v1/projects/{project_id}
```

### 1.5 获取项目详情
```
GET /api/v1/projects/{project_id}
```

---

## 2. 需求文档 API

### 2.1 上传需求文档
```
POST /api/v1/projects/{project_id}/documents
```

**请求类型**: `multipart/form-data`

**请求参数:**
| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| file | File | 是 | PDF或Word文件 |
| title | string | 否 | 文档标题 |

**响应示例:**
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": 1,
    "project_id": 1,
    "title": "用户注册需求",
    "file_type": "pdf",
    "file_size": 1024000,
    "extracted_text": "需求内容...",
    "created_at": "2024-03-09T12:00:00Z"
  }
}
```

### 2.2 获取项目文档列表
```
GET /api/v1/projects/{project_id}/documents
```

### 2.3 删除文档
```
DELETE /api/v1/documents/{document_id}
```

### 2.4 获取文档详情
```
GET /api/v1/documents/{document_id}
```

---

## 3. 测试用例 API

### 3.1 AI生成测试用例
```
POST /api/v1/documents/{document_id}/generate-testcases
```

**请求参数:**
```json
{
  "model": "qwen3.5-flash",
  "provider": "qwen",
  "max_cases": 20
}
```

**响应示例:**
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "task_id": "uuid",
    "status": "generating",
    "generated_cases": [
      {
        "name": "用户正常注册",
        "description": "测试用户使用有效信息完成注册",
        "precondition": "用户未注册",
        "steps": ["打开注册页面", "输入用户名", "输入密码", "点击注册"],
        "expected_result": "注册成功，跳转到首页",
        "priority": "high"
      }
    ]
  }
}
```

### 3.2 保存测试用例
```
POST /api/v1/projects/{project_id}/testcases
```

**请求参数:**
```json
{
  "name": "测试用例名称",
  "description": "描述",
  "precondition": "前置条件",
  "steps": ["步骤1", "步骤2"],
  "expected_result": "预期结果",
  "priority": "high",
  "tags": ["功能测试", "冒烟测试"]
}
```

### 3.3 批量保存测试用例
```
POST /api/v1/projects/{project_id}/testcases/batch
```

### 3.4 获取测试用例列表
```
GET /api/v1/projects/{project_id}/testcases
```

**查询参数:**
| 参数名 | 类型 | 说明 |
|--------|------|------|
| page | int | 页码 |
| page_size | int | 每页数量 |
| priority | string | 优先级筛选 |
| keyword | string | 关键词搜索 |
| status | string | 状态筛选 |

### 3.5 获取测试用例详情
```
GET /api/v1/testcases/{testcase_id}
```

### 3.6 更新测试用例
```
PUT /api/v1/testcases/{testcase_id}
```

### 3.7 删除测试用例
```
DELETE /api/v1/testcases/{testcase_id}
```

### 3.8 批量删除测试用例
```
DELETE /api/v1/testcases
```

**请求参数:**
```json
{
  "ids": [1, 2, 3]
}
```

---

## 4. 测试执行 API

### 4.1 执行单个测试用例
```
POST /api/v1/testcases/{testcase_id}/execute
```

**请求参数:**
```json
{
  "provider": "qwen",
  "model": "qwen3.5-flash",
  "enable_screenshots": true
}
```

**响应示例:**
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "execution_id": "uuid",
    "testcase_id": 1,
    "status": "running"
  }
}
```

### 4.2 批量执行测试用例
```
POST /api/v1/testcases/batch-execute
```

**请求参数:**
```json
{
  "testcase_ids": [1, 2, 3],
  "provider": "qwen",
  "model": "qwen3.5-flash",
  "enable_screenshots": true
}
```

### 4.3 停止测试执行
```
POST /api/v1/executions/{execution_id}/stop
```

### 4.4 获取执行状态
```
GET /api/v1/executions/{execution_id}
```

### 4.5 WebSocket 实时更新
```
WS /api/v1/ws/executions/{execution_id}
```

**消息类型:**
- `execution_started`: 执行开始
- `step_update`: 步骤更新
- `screenshot_update`: 截图更新
- `testcase_completed`: 用例完成
- `execution_completed`: 执行完成
- `execution_failed`: 执行失败

---

## 5. 测试报告 API

### 5.1 获取测试报告列表
```
GET /api/v1/projects/{project_id}/reports
```

**查询参数:**
| 参数名 | 类型 | 说明 |
|--------|------|------|
| page | int | 页码 |
| page_size | int | 每页数量 |
| start_date | string | 开始日期 |
| end_date | string | 结束日期 |

### 5.2 获取报告详情
```
GET /api/v1/reports/{report_id}
```

**响应示例:**
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": 1,
    "project_id": 1,
    "name": "测试报告-20240309",
    "status": "completed",
    "total_cases": 10,
    "passed_cases": 8,
    "failed_cases": 2,
    "skipped_cases": 0,
    "pass_rate": 80.0,
    "start_time": "2024-03-09T10:00:00Z",
    "end_time": "2024-03-09T10:30:00Z",
    "duration": 1800,
    "executions": [...]
  }
}
```

### 5.3 导出测试报告
```
GET /api/v1/reports/{report_id}/export
```

**查询参数:**
| 参数名 | 类型 | 说明 |
|--------|------|------|
| format | string | 导出格式 (pdf/excel/html) |

---

## 6. 统计分析 API

### 6.1 获取项目统计数据
```
GET /api/v1/projects/{project_id}/statistics
```

**响应示例:**
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "project_id": 1,
    "total_testcases": 50,
    "total_executions": 200,
    "recent_pass_rate": 85.5,
    "today_executions": 10,
    "weekly_trend": [...]
  }
}
```

### 6.2 获取执行趋势
```
GET /api/v1/projects/{project_id}/trend
```

**查询参数:**
| 参数名 | 类型 | 说明 |
|--------|------|------|
| days | int | 统计天数 |

---

## 7. 系统配置 API

### 7.1 获取系统配置
```
GET /api/v1/config
```

### 7.2 更新系统配置
```
PUT /api/v1/config
```

**请求参数:**
```json
{
  "default_model": "qwen3.5-flash",
  "default_provider": "qwen",
  "max_execution_time": 3600,
  "screenshot_enabled": true
}
```

---

## 通用响应格式

### 成功响应
```json
{
  "code": 0,
  "message": "success",
  "data": {...}
}
```

### 错误响应
```json
{
  "code": 40001,
  "message": "错误描述",
  "data": null
}
```

### 错误码
| 错误码 | 说明 |
|--------|------|
| 40001 | 参数错误 |
| 40002 | 资源不存在 |
| 40003 | 文件格式不支持 |
| 40004 | AI生成失败 |
| 40005 | 执行超时 |
| 50001 | 服务器内部错误 |
