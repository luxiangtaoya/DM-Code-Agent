# AI测试平台 API 接口文档

## 基础信息
- 基础路径：`/api`
- 数据格式：JSON
- 认证方式：暂无（单用户模式）

---

## 1. 项目管理 API

### 1.1 获取项目列表
```
GET /projects
```

**响应示例：**
```json
{
  "code": 0,
  "message": "success",
  "data": [
    {
      "id": 1,
      "name": "电商项目",
      "description": "电商平台功能测试",
      "created_at": "2024-01-01T00:00:00Z",
      "updated_at": "2024-01-01T00:00:00Z",
      "test_case_count": 15
    }
  ]
}
```

### 1.2 创建项目
```
POST /projects
```

**请求参数：**
```json
{
  "name": "项目名称",
  "description": "项目描述"
}
```

### 1.3 更新项目
```
PUT /projects/{project_id}
```

### 1.4 删除项目
```
DELETE /projects/{project_id}
```

### 1.5 获取项目详情
```
GET /projects/{project_id}
```

---

## 2. 需求文档 API

### 2.1 上传需求文档
```
POST /projects/{project_id}/documents
```

**请求类型：** `multipart/form-data`

**请求参数：**
| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| file | File | 是 | PDF或Word文件 |
| title | string | 否 | 文档标题，默认使用文件名 |

**响应示例：**
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": 1,
    "project_id": 1,
    "title": "用户注册需求文档",
    "file_path": "/uploads/documents/xxx.pdf",
    "file_type": "pdf",
    "extracted_text": "提取的文本内容...",
    "created_at": "2024-01-01T00:00:00Z"
  }
}
```

### 2.2 获取项目文档列表
```
GET /projects/{project_id}/documents
```

### 2.3 删除文档
```
DELETE /documents/{document_id}
```

### 2.4 获取文档详情
```
GET /documents/{document_id}
```

---

## 3. 测试用例 API

### 3.1 AI生成测试用例
```
POST /documents/{document_id}/generate-testcases
```

**请求参数：**
```json
{
  "model": "qwen3.5-flash",
  "provider": "qwen"
}
```

**响应示例：**
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "task_id": "xxx-uuid",
    "status": "generating",
    "generated_cases": [
      {
        "name": "用户正常注册",
        "description": "测试用户使用有效信息完成注册流程",
        "precondition": "用户未注册",
        "steps": [
          "打开注册页面",
          "输入用户名",
          "输入密码",
          "点击注册按钮"
        ],
        "expected_result": "注册成功，跳转到首页",
        "priority": "high"
      }
    ]
  }
}
```

### 3.2 保存测试用例
```
POST /projects/{project_id}/testcases
```

**请求参数：**
```json
{
  "name": "测试用例名称",
  "description": "描述",
  "precondition": "前置条件",
  "steps": ["步骤1", "步骤2"],
  "expected_result": "预期结果",
  "priority": "high|medium|low",
  "tags": ["功能测试", "冒烟测试"]
}
```

### 3.3 获取项目测试用例列表
```
GET /projects/{project_id}/testcases
```

**查询参数：**
| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| page | int | 否 | 页码，默认1 |
| page_size | int | 否 | 每页数量，默认20 |
| priority | string | 否 | 筛选优先级 |
| keyword | string | 否 | 搜索关键词 |

### 3.4 获取测试用例详情
```
GET /testcases/{testcase_id}
```

### 3.5 更新测试用例
```
PUT /testcases/{testcase_id}
```

### 3.6 删除测试用例
```
DELETE /testcases/{testcase_id}
```

### 3.7 批量删除测试用例
```
DELETE /testcases
```

**请求参数：**
```json
{
  "ids": [1, 2, 3]
}
```

---

## 4. 测试执行 API

### 4.1 执行单个测试用例
```
POST /testcases/{testcase_id}/execute
```

**请求参数：**
```json
{
  "provider": "qwen",
  "model": "qwen3.5-flash",
  "enable_screenshots": true
}
```

**响应示例：**
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "execution_id": "xxx-uuid",
    "testcase_id": 1,
    "status": "running"
  }
}
```

### 4.2 批量执行测试用例
```
POST /testcases/batch-execute
```

**请求参数：**
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
POST /executions/{execution_id}/stop
```

### 4.4 获取执行状态
```
GET /executions/{execution_id}
```

### 4.5 WebSocket 实时更新
```
WS /ws/executions/{execution_id}
```

**消息类型：**
- `execution_started`: 执行开始
- `step_update`: 步骤更新
- `testcase_completed`: 用例完成
- `execution_completed`: 执行完成
- `execution_failed`: 执行失败

---

## 5. 测试报告 API

### 5.1 获取项目测试报告列表
```
GET /projects/{project_id}/reports
```

### 5.2 获取执行报告详情
```
GET /reports/{report_id}
```

**响应示例：**
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": 1,
    "execution_id": "xxx-uuid",
    "project_id": 1,
    "status": "completed",
    "total_cases": 10,
    "passed_cases": 8,
    "failed_cases": 2,
    "skipped_cases": 0,
    "pass_rate": 80.0,
    "start_time": "2024-01-01T00:00:00Z",
    "end_time": "2024-01-01T00:05:00Z",
    "duration": 300,
    "cases": [
      {
        "testcase_id": 1,
        "name": "用户正常注册",
        "status": "passed",
        "steps": [...],
        "error_message": null,
        "screenshot_path": "/screenshots/xxx.png"
      }
    ]
  }
}
```

### 5.3 获取测试统计
```
GET /projects/{project_id}/statistics
```

---

## 6. 通用响应格式

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
| 50001 | 服务器内部错误 |
