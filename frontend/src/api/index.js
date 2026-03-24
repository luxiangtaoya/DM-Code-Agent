import axios from 'axios'
import { Message } from 'element-ui'

// 创建axios实例
const request = axios.create({
  baseURL: process.env.VUE_APP_API_BASE_URL || 'http://localhost:8080/api/v1',
  timeout: 60000
})

// 请求拦截器
request.interceptors.request.use(
  config => {
    return config
  },
  error => {
    console.error('请求错误:', error)
    return Promise.reject(error)
  }
)

// 响应拦截器
request.interceptors.response.use(
  response => {
    const res = response.data

    // 如果code不为0，显示错误信息
    if (res.code !== undefined && res.code !== 0) {
      Message.error(res.message || '请求失败')
      return Promise.reject(new Error(res.message || '请求失败'))
    }

    return res
  },
  error => {
    console.error('响应错误:', error)

    if (error.response) {
      const status = error.response.status
      let message = '请求失败'

      switch (status) {
        case 400:
          message = '请求参数错误'
          break
        case 404:
          message = '请求的资源不存在'
          break
        case 500:
          message = '服务器内部错误'
          break
        default:
          message = error.response.data?.detail || '请求失败'
      }

      Message.error(message)
    } else if (error.request) {
      Message.error('网络错误，请检查网络连接')
    } else {
      Message.error(error.message || '请求失败')
    }

    return Promise.reject(error)
  }
)

// ==================== 项目API ====================

export const projectApi = {
  // 获取项目列表
  getList() {
    return request.get('/projects')
  },

  // 获取项目详情
  getDetail(projectId) {
    return request.get(`/projects/${projectId}`)
  },

  // 创建项目
  create(data) {
    return request.post('/projects', data)
  },

  // 更新项目
  update(projectId, data) {
    return request.put(`/projects/${projectId}`, data)
  },

  // 删除项目
  delete(projectId) {
    return request.delete(`/projects/${projectId}`)
  },

  // 获取项目统计数据
  getStatistics(projectId) {
    return request.get(`/projects/${projectId}/statistics`)
  }
}

// ==================== 文档API ====================

export const documentApi = {
  // 上传文档
  upload(projectId, file, title) {
    const formData = new FormData()
    formData.append('file', file)
    if (title) {
      formData.append('title', title)
    }
    return request.post(`/projects/${projectId}/documents`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
  },

  // 获取项目文档列表
  getList(projectId) {
    return request.get(`/projects/${projectId}/documents`)
  },

  // 删除文档
  delete(documentId) {
    return request.delete(`/documents/${documentId}`)
  },

  // 生成测试用例
  generateTestCases(documentId, data) {
    return request.post(`/documents/${documentId}/generate-testcases`, data)
  }
}

// ==================== 测试用例API ====================

export const testCaseApi = {
  // 获取测试用例列表
  getList(projectId, params) {
    return request.get(`/projects/${projectId}/testcases`, { params })
  },

  // 获取测试用例详情
  getDetail(testCaseId) {
    return request.get(`/testcases/${testCaseId}`)
  },

  // 获取测试用例的最新执行记录
  getLatestExecution(testCaseId) {
    return request.get(`/testcases/${testCaseId}/latest-execution`)
  },

  // 创建测试用例
  create(projectId, data) {
    return request.post(`/projects/${projectId}/testcases`, data)
  },

  // 批量创建测试用例
  batchCreate(projectId, cases) {
    return request.post(`/projects/${projectId}/testcases/batch`, cases)
  },

  // 更新测试用例
  update(testCaseId, data) {
    return request.put(`/testcases/${testCaseId}`, data)
  },

  // 删除测试用例
  delete(testCaseId) {
    return request.delete(`/testcases/${testCaseId}`)
  },

  // 批量删除测试用例
  batchDelete(ids) {
    return request.delete('/testcases', { data: { ids } })
  },

  // 批量执行测试用例（支持单个或多个）
  batchExecute(testcaseIds, data) {
    return request.post('/testcases/batch-execute', { testcase_ids: testcaseIds, ...data })
  },

  // 获取测试用例状态
  getStatus(testCaseId) {
    return request.get(`/testcases/${testCaseId}/status`)
  },

  // Excel导入测试用例
  importExcel(projectId, formData) {
    return request.post(`/projects/${projectId}/testcases/import/excel`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
  }
}

// ==================== 执行记录API ====================

export const executionApi = {
  // 获取项目执行记录列表
  getList(projectId, params, options = {}) {
    return request.get(`/projects/${projectId}/executions`, { params, ...options })
  },

  // 获取执行详情
  getDetail(executionId) {
    return request.get(`/executions/${executionId}`)
  },

  // 获取执行状态
  getStatus(executionId) {
    return request.get(`/executions/${executionId}`)
  },

  // 获取测试用例状态（用于轮询）
  getTestcaseStatus(testCaseId) {
    return request.get(`/testcases/${testCaseId}/status`)
  },

  // 获取 GIF - 支持两种参数：
  // 1. 传入 gif_path（如 /screenshots/xxx/output.gif）- 直接返回完整 URL
  // 2. 传入 executionId - 调用 API 端点获取
  getGif(pathOrId) {
    if (!pathOrId) return ''
    // 如果是路径（以/开头），直接返回完整 URL
    if (pathOrId.startsWith('/screenshots')) {
      return (process.env.VUE_APP_API_BASE_URL || 'http://localhost:8080/api/v1') + pathOrId
    }
    // 否则作为 executionId 调用 API
    return `${process.env.VUE_APP_API_BASE_URL || 'http://localhost:8080/api/v1'}/executions/${pathOrId}/gif`
  },

  // 获取WebSocket URL
  getWsUrl(executionId) {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsHost = process.env.VUE_APP_WS_HOST || window.location.hostname
    const wsPort = process.env.VUE_APP_WS_PORT || 8001
    return `${wsProtocol}//${wsHost}:${wsPort}/api/v1/ws/executions/${executionId}`
  },

  // 停止执行
  stop(executionId) {
    return request.post(`/executions/${executionId}/stop`)
  },

  // 删除单条执行记录
  delete(executionId) {
    return request.delete(`/executions/${executionId}`)
  },

  // 批量删除执行记录
  batchDelete(ids) {
    return request.delete('/executions', { data: { ids } })
  }
}

// ==================== 报告API ====================

export const reportApi = {
  // 获取报告列表
  getList(projectId, params) {
    return request.get(`/projects/${projectId}/reports`, { params })
  },

  // 获取报告详情
  getDetail(reportId) {
    return request.get(`/reports/${reportId}`)
  },

  // 导出报告
  export(reportId, format) {
    return request.get(`/reports/${reportId}/export`, {
      params: { format },
      responseType: 'blob'
    })
  },

  // 获取项目统计数据
  getStatistics(projectId, params) {
    return request.get(`/projects/${projectId}/reports/statistics`, { params })
  },

  // 分析缺陷
  analyzeDefect(testCaseId, params) {
    return request.post(`/testcases/${testCaseId}/analyze-defect`, params)
  },

  // 获取缺陷分析历史
  getDefectAnalyses(testCaseId) {
    return request.get(`/testcases/${testCaseId}/defect-analyses`)
  }
}

export default request
