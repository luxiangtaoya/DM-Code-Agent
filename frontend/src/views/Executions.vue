<template>
  <div class="executions-page">
    <div class="page-header">
      <h2>执行记录</h2>
      <div>
        <el-button 
          type="danger" 
          size="small" 
          @click="batchDeleteExecutions" 
          :disabled="selectedExecutions.length === 0"
          v-if="selectedExecutions.length > 0">
          <i class="el-icon-delete"></i> 批量删除 ({{ selectedExecutions.length }})
        </el-button>
        <el-button type="primary" @click="showExecuteDialog = true" :disabled="!hasCurrentProject">
          <i class="el-icon-video-play"></i> 执行测试用例
        </el-button>
      </div>
    </div>

    <!-- 筛选条件 -->
    <el-card class="filter-card" shadow="never">
      <el-form :inline="true" :model="filters" class="filter-form">
        <el-form-item label="状态">
          <el-select v-model="filters.status" placeholder="全部" clearable @change="loadExecutions">
            <el-option label="全部" value=""></el-option>
            <el-option label="等待中" value="pending"></el-option>
            <el-option label="运行中" value="running"></el-option>
            <el-option label="已完成" value="completed"></el-option>
            <el-option label="失败" value="failed"></el-option>
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button icon="el-icon-refresh" @click="loadExecutions" :loading="refreshing">刷新</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 执行记录列表 -->
    <el-card class="table-card" shadow="never">
      <el-table :data="executions" v-loading="loading" stripe @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="55"></el-table-column>
        <el-table-column prop="testcase_name" label="测试用例" min-width="200"></el-table-column>
        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">
              {{ getStatusText(row.status, row.result) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="result" label="结果" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.result" :type="row.result === 'passed' ? 'success' : 'danger'" size="small">
              {{ getResultText(row.result) }}
            </el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="model" label="模型" width="150"></el-table-column>
        <el-table-column prop="provider" label="提供商" width="100"></el-table-column>
        <el-table-column prop="created_at" label="添加时间" width="180">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column prop="duration" label="耗时" width="100">
          <template #default="{ row }">
            {{ formatDuration(row.duration) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="300" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" size="mini" @click="viewTestCaseDetail(row.testcase_id)">查看详情</el-button>
            <el-button type="success" size="mini" @click="viewExecutionResult(row.id)">执行结果</el-button>
            <el-button type="danger" size="mini" @click="deleteExecution(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-if="total > 0"
        :current-page="pagination.page"
        :page-size="pagination.pageSize"
        :total="total"
        @current-change="handlePageChange"
        layout="total, prev, pager, next">
      </el-pagination>
    </el-card>

    <!-- 执行测试用例对话框 -->
    <el-dialog title="执行测试用例" :visible.sync="showExecuteDialog" width="600px" @close="resetExecuteForm">
      <el-form :model="executeForm" :rules="executeRules" ref="executeFormRef" label-width="100px">
        <el-form-item label="测试用例" prop="testcaseIds" required>
          <el-select
            v-model="executeForm.testcaseIds"
            multiple
            collapse-tags
            placeholder="请选择要执行的测试用例"
            style="width: 100%">
            <el-option
              v-for="tc in testCases"
              :key="tc.id"
              :label="tc.name"
              :value="tc.id">
              <span>{{ tc.name }}</span>
              <span style="color: #8492a6; font-size: 12px; margin-left: 10px">{{ tc.priority }}</span>
            </el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="AI 模型" prop="model">
          <el-input v-model="executeForm.model" placeholder="例如：qwen3.5-flash"></el-input>
        </el-form-item>
        <el-form-item label="提供商" prop="provider">
          <el-select v-model="executeForm.provider" placeholder="选择提供商">
            <el-option label="Qwen" value="qwen"></el-option>
            <el-option label="OpenAI" value="openai"></el-option>
            <el-option label="Claude" value="claude"></el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="启用截图" prop="enableScreenshots">
          <el-switch v-model="executeForm.enableScreenshots"></el-switch>
        </el-form-item>
      </el-form>
      <div slot="footer">
        <el-button @click="showExecuteDialog = false">取消</el-button>
        <el-button type="primary" @click="executeTestCases" :loading="executing">执行</el-button>
      </div>
    </el-dialog>

    <!-- 执行结果对话框 - 简化版 -->
    <el-dialog
      title="执行结果"
      :visible.sync="showProgressDialog"
      width="600px"
      :close-on-click-modal="false">
      <div v-for="exec in runningExecutions" :key="exec.testcaseId" class="execution-item">
        <div class="execution-header">
          <span class="execution-name">{{ exec.testcaseName }}</span>
          <el-tag :type="getStatusType(exec.status)" size="small">{{ getStatusText(exec.status) }}</el-tag>
        </div>
        <div v-if="exec.status === '执行通过'" class="execution-result">
          <el-alert
            type="success"
            title="测试通过"
            :description="exec.finalAnswer || '测试用例执行通过'"
            :closable="false"
            show-icon>
          </el-alert>
          <div v-if="exec.gifPath" class="execution-gif">
            <h4>执行 GIF:</h4>
            <img :src="exec.gifPath" alt="execution gif" style="width: 100%; margin-top: 10px;" />
          </div>
        </div>
        <div v-if="exec.status === '执行不通过'" class="execution-result">
          <el-alert
            type="error"
            title="测试不通过"
            :description="exec.finalAnswer || '测试用例执行不通过'"
            :closable="false"
            show-icon>
          </el-alert>
        </div>
        <div v-if="exec.status === '执行失败' && exec.errorMessage" class="error-message">
          <el-alert
            type="error"
            title="执行失败"
            :description="exec.errorMessage"
            :closable="false"
            show-icon>
          </el-alert>
        </div>
        <div v-if="exec.status === '执行中'" class="running-status">
          <p>任务正在执行中，请稍候...</p>
        </div>
        <div v-if="exec.status === '等待执行'" class="running-status">
          <p>任务正在等待执行，请稍候...</p>
        </div>
      </div>
      <div slot="footer">
        <el-button type="primary" @click="showProgressDialog = false; loadExecutions()">关闭</el-button>
      </div>
    </el-dialog>

    <!-- 查看执行详情对话框 -->
    <el-dialog title="执行详情" :visible.sync="showDetailDialog" width="900px">
      <div v-if="currentExecution" class="execution-detail">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="测试用例">{{ currentExecution.testcase_name }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="getStatusType(currentExecution.status)" size="small">
              {{ getStatusText(currentExecution.status, currentExecution.result) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="结果">
            <el-tag v-if="currentExecution.result" :type="currentExecution.result === 'passed' ? 'success' : 'danger'" size="small">
              {{ getResultText(currentExecution.result) }}
            </el-tag>
            <span v-else>-</span>
          </el-descriptions-item>
          <el-descriptions-item label="模型">{{ currentExecution.model }}</el-descriptions-item>
          <el-descriptions-item label="提供商">{{ currentExecution.provider }}</el-descriptions-item>
          <el-descriptions-item label="添加时间">{{ formatTime(currentExecution.created_at) }}</el-descriptions-item>
          <el-descriptions-item label="耗时">{{ formatDuration(currentExecution.duration) }}</el-descriptions-item>
        </el-descriptions>

        <div v-if="currentExecution.steps_log && currentExecution.steps_log.length > 0" class="steps-log-section">
          <h3>执行步骤:</h3>
          <el-collapse v-model="activeSteps">
            <el-collapse-item
              v-for="(step, index) in currentExecution.steps_log"
              :key="index"
              :name="index">
              <template slot="title">
                <span class="step-number">{{ index + 1 }}.</span>
                <span class="step-abbreviation">{{ step.step_abbreviation || step.action || '未知步骤' }}</span>
                <el-tag size="mini" :type="step.observation && step.observation.includes('失败') ? 'danger' : 'success'" class="step-status-tag">
                  {{ step.observation && step.observation.includes('失败') ? '失败' : '成功' }}
                </el-tag>
              </template>
              <div class="step-detail">
                <div class="detail-item" v-if="step.thought">
                  <strong>思考：</strong>
                  <p>{{ step.thought }}</p>
                </div>
                <div class="detail-item">
                  <strong>动作：</strong>
                  <p>{{ step.action }}</p>
                </div>
                <div class="detail-item" v-if="step.action_input">
                  <strong>输入参数：</strong>
                  <pre>{{ formatActionInput(step.action_input) }}</pre>
                </div>
                <div class="detail-item">
                  <strong>观察结果：</strong>
                  <p>{{ step.observation }}</p>
                </div>
              </div>
            </el-collapse-item>
          </el-collapse>
        </div>

        <div v-if="currentExecution.gif_path" class="detail-gif">
          <h3>执行 GIF:</h3>
          <img :src="getExecutionGif(currentExecution.gif_path)" alt="execution gif" />
        </div>

        <div v-if="currentExecution.error_message" class="error-message">
          <el-alert
            type="error"
            title="错误信息"
            :description="currentExecution.error_message"
            :closable="false"
            show-icon>
          </el-alert>
        </div>

        <div v-if="currentExecution.final_answer" class="final-answer">
          <el-alert
            :type="currentExecution.result === 'passed' ? 'success' : 'error'"
            :title="currentExecution.result === 'passed' ? '测试通过' : '测试失败'"
            :description="currentExecution.final_answer"
            :closable="false"
            show-icon>
          </el-alert>
        </div>
      </div>
    </el-dialog>

    <!-- 查看测试用例详情对话框 -->
    <el-dialog title="测试用例详情" :visible.sync="showTestCaseDetailDialog" width="900px">
      <div v-if="viewingTestCase" class="testcase-detail">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="用例名称">{{ viewingTestCase.name }}</el-descriptions-item>
          <el-descriptions-item label="优先级">
            <el-tag :type="viewingTestCase.priority === 'P1' ? 'danger' : viewingTestCase.priority === 'P2' ? 'warning' : 'info'" size="small">
              {{ viewingTestCase.priority }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="用例类型">{{ viewingTestCase.case_type }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="getStatusType(viewingTestCase.status)" size="small">
              {{ getStatusText(viewingTestCase.status) }}
            </el-tag>
          </el-descriptions-item>
        </el-descriptions>

        <el-divider>前置条件</el-divider>
        <p>{{ viewingTestCase.precondition || '无' }}</p>

        <el-divider>测试步骤</el-divider>
        <div class="steps-list">
          <div v-for="(step, index) in viewingTestCase.steps" :key="index" class="step-item">
            <span class="step-number">{{ index + 1 }}.</span>
            <span>{{ step }}</span>
          </div>
        </div>

        <el-divider>预期结果</el-divider>
        <p>{{ viewingTestCase.expected_result }}</p>

        <el-divider v-if="viewingTestCase.description">用例描述</el-divider>
        <p v-if="viewingTestCase.description">{{ viewingTestCase.description }}</p>
      </div>
    </el-dialog>

    <!-- GIF 查看对话框 -->
    <el-dialog title="执行 GIF" :visible.sync="showGifDialog" width="600px">
      <div v-if="currentGif" class="gif-viewer">
        <img :src="currentGif" alt="execution gif" style="width: 100%" />
      </div>
    </el-dialog>
  </div>
</template>

<script>
import { mapState, mapGetters } from 'vuex'
import { testCaseApi, executionApi } from '@/api'

export default {
  name: 'Executions',
  data() {
    return {
      executions: [],
      testCases: [],
      loading: false,
      executing: false,
      refreshing: false,
      total: 0,
      pagination: {
        page: 1,
        pageSize: 20
      },
      filters: {
        status: ''
      },
      showExecuteDialog: false,
      showProgressDialog: false,
      showDetailDialog: false,
      showGifDialog: false,
      executeForm: {
        testcaseIds: [],
        model: 'qwen3.5-flash',
        provider: 'qwen',
        enableScreenshots: true
      },
      executeRules: {
        testcaseIds: [{ required: true, message: '请选择测试用例', trigger: 'change' }]
      },
      runningExecutions: [],
      currentExecution: null,
      currentGif: '',
      showTestCaseDetailDialog: false,
      viewingTestCase: null,
      selectedExecutions: [],
      activeSteps: []
    }
  },
  computed: {
    ...mapState(['currentProject']),
    ...mapGetters(['hasCurrentProject'])
  },
  mounted() {
    if (this.hasCurrentProject) {
      this.loadExecutions()
      this.loadTestCases()
    }
  },
  watch: {
    currentProject(newVal) {
      if (newVal) {
        this.loadExecutions()
        this.loadTestCases()
      }
    }
  },
  methods: {
    async loadExecutions() {
      if (!this.currentProject) return

      this.loading = true
      this.refreshing = true
      try {
        const params = {
          page: this.pagination.page,
          page_size: this.pagination.pageSize,
          ...this.filters
        }
        // 使用更短的超时时间，避免刷新按钮被长时间阻塞
        const response = await executionApi.getList(this.currentProject.id, params, { timeout: 5000 })
        this.executions = response.data.items
        this.total = response.data.total
      } catch (error) {
        if (error.code === 'ECONNABORTED') {
          this.$message.warning('刷新超时，请稍后重试')
        } else {
          this.$message.error('加载执行记录失败')
        }
      } finally {
        this.loading = false
        this.refreshing = false
      }
    },

    async loadTestCases() {
      if (!this.currentProject) return

      try {
        const response = await testCaseApi.getList(this.currentProject.id, { page_size: 1000 })
        this.testCases = response.data.items
      } catch (error) {
        console.error('加载测试用例失败:', error)
      }
    },

    handlePageChange(page) {
      this.pagination.page = page
      this.loadExecutions()
    },

    async executeTestCases() {
      this.$refs.executeFormRef.validate(async (valid) => {
        if (!valid) return

        this.executing = true
        this.showExecuteDialog = false
        this.showProgressDialog = true

        try {
          // 调用批量执行接口（一次请求）
          const response = await testCaseApi.batchExecute(this.executeForm.testcaseIds, {
            model: this.executeForm.model,
            provider: this.executeForm.provider,
            enable_screenshots: this.executeForm.enableScreenshots
          })

          // 为每个 testcase 创建显示引用
          for (const testcaseId of this.executeForm.testcaseIds) {
            const testcase = this.testCases.find(tc => tc.id === testcaseId)
            const executionRef = {
              testcaseId,
              testcaseName: testcase?.name || `测试用例 ${testcaseId}`,
              status: '等待执行',
              result: null,
              finalAnswer: null,
              errorMessage: null,
              gifPath: null
            }
            this.runningExecutions.push(executionRef)
            this.pollExecutionStatus(testcaseId, executionRef)
          }

          this.$notify.success({
            title: '执行开始',
            message: `已添加 ${response.data.updated_count} 个测试用例到执行队列`,
            duration: 3000
          })
        } catch (error) {
          this.$message.error(`批量执行失败：${error.message || error}`)
        }

        this.executing = false
        this.resetExecuteForm()
      })
    },

    pollExecutionStatus(testcaseId, executionRef) {
      const poll = async () => {
        try {
          const response = await executionApi.getTestcaseStatus(testcaseId)
          const data = response.data

          // 更新显示状态（test_cases 表的状态是中文）
          executionRef.status = data.status || '等待执行'
          executionRef.gifPath = data.gif_path

          // 检查是否执行完成
          if (data.status === '执行通过') {
            executionRef.result = 'passed'
            executionRef.finalAnswer = '测试通过'
            this.$notify.success({
              title: '执行完成',
              message: `${executionRef.testcaseName} - 执行通过`,
              duration: 3000
            })
            this.loadExecutions()
          } else if (data.status === '执行不通过') {
            executionRef.result = 'failed'
            executionRef.finalAnswer = '测试不通过'
            this.$notify.error({
              title: '执行完成',
              message: `${executionRef.testcaseName} - 执行不通过`,
              duration: 3000
            })
            this.loadExecutions()
          } else if (data.status === '执行失败') {
            executionRef.status = 'failed'
            executionRef.result = 'failed'
            executionRef.errorMessage = '执行失败，请查看日志'
            this.$notify.error({
              title: '执行失败',
              message: `${executionRef.testcaseName} - 执行失败`,
              duration: 3000
            })
            this.loadExecutions()
          } else if (data.status === '执行中') {
            // 继续轮询
            setTimeout(poll, 3000)
          } else if (data.status === '待测试' || data.status === '等待执行') {
            // 继续轮询
            setTimeout(poll, 3000)
          }
        } catch (error) {
          console.error(`轮询测试用例状态失败：${testcaseId}`, error)
        }
      }

      // 首次立即轮询
      setTimeout(poll, 2000)
    },

    async viewExecution(row) {
      try {
        const response = await executionApi.getStatus(row.id)
        this.currentExecution = response.data
        this.showDetailDialog = true
      } catch (error) {
        this.$message.error('加载执行详情失败')
      }
    },

    viewGif(row) {
      // row.gif_path 已经是完整路径如 /screenshots/xxx/output.gif
      this.currentGif = executionApi.getGif(row.gif_path)
      this.showGifDialog = true
    },

    resetExecuteForm() {
      this.executeForm = {
        testcaseIds: [],
        model: 'qwen3.5-flash',
        provider: 'qwen',
        enableScreenshots: true
      }
      this.$refs.executeFormRef?.clearValidate()
    },

    getStatusType(status) {
      const typeMap = {
        pending: 'info',
        running: 'warning',
        completed: 'success',
        failed: 'danger'
      }
      return typeMap[status] || 'info'
    },

    getStatusText(status, result) {
      const textMap = {
        pending: '等待中',
        running: '运行中',
        completed: '已完成',
        failed: '执行失败'
      }
      // 如果是 completed 状态，根据 result 显示更详细的信息
      if (status === 'completed' && result === 'passed') {
        return '执行通过'
      }
      if (status === 'completed' && result === 'failed') {
        return '执行不通过'
      }
      return textMap[status] || status
    },

    getResultText(result) {
      const textMap = {
        passed: '通过',
        failed: '未通过'
      }
      return textMap[result] || result
    },

    formatTime(time) {
      if (!time) return '-'
      try {
        const date = new Date(time)
        return date.toLocaleString('zh-CN', {
          year: 'numeric',
          month: '2-digit',
          day: '2-digit',
          hour: '2-digit',
          minute: '2-digit'
        })
      } catch {
        return time
      }
    },

    formatDuration(seconds) {
      if (!seconds || seconds < 0) return '-'
      if (seconds < 60) return `${seconds}秒`
      const minutes = Math.floor(seconds / 60)
      const remainingSeconds = seconds % 60
      if (remainingSeconds === 0) return `${minutes}分`
      return `${minutes}分${remainingSeconds}秒`
    },

    // 处理表格选择变化
    handleSelectionChange(selection) {
      this.selectedExecutions = selection
    },

    // 查看测试用例详情
    async viewTestCaseDetail(testcaseId) {
      try {
        const response = await testCaseApi.getDetail(testcaseId)
        this.viewingTestCase = response.data
        this.showTestCaseDetailDialog = true
      } catch (error) {
        this.$message.error('加载测试用例详情失败')
      }
    },

    // 查看执行结果
    async viewExecutionResult(executionId) {
      try {
        const response = await executionApi.getDetail(executionId)
        this.currentExecution = response.data
        this.showDetailDialog = true
      } catch (error) {
        this.$message.error('加载执行详情失败')
      }
    },

    // 删除单条执行记录
    async deleteExecution(executionId) {
      try {
        await this.$confirm('确认删除该执行记录？', '提示', { type: 'warning' })
        await executionApi.delete(executionId)
        this.$message.success('删除成功')
        this.loadExecutions()
      } catch (error) {
        if (error !== 'cancel') {
          this.$message.error('删除失败')
        }
      }
    },

    getExecutionGif(pathOrId) {
      if (!pathOrId) return ''
      // 如果已经是相对路径（如 /screenshots/xxx/task_animation.gif），直接返回
      // vue.config.js 已配置代理，会转发到 http://localhost:8080/screenshots/...
      if (pathOrId.startsWith('/')) {
        return pathOrId
      }
      // 如果是相对路径但没有开头 /（如 screenshots/xxx/task_animation.gif），添加 /
      if (pathOrId.startsWith('screenshots')) {
        return '/' + pathOrId
      }
      // 如果已经是完整URL，直接返回
      if (pathOrId.startsWith('http://') || pathOrId.startsWith('https://')) {
        return pathOrId
      }
      return ''
    },

    formatActionInput(input) {
      if (!input) return ''
      try {
        if (typeof input === 'string') {
          return input
        }
        return JSON.stringify(input, null, 2)
      } catch {
        return String(input)
      }
    },

    // 批量删除执行记录
    async batchDeleteExecutions() {
      try {
        await this.$confirm(`确认删除选中的 ${this.selectedExecutions.length} 条执行记录？`, '提示', { type: 'warning' })
        const ids = this.selectedExecutions.map(e => e.id)
        await executionApi.batchDelete(ids)
        this.$message.success('批量删除成功')
        this.selectedExecutions = []
        this.loadExecutions()
      } catch (error) {
        if (error !== 'cancel') {
          this.$message.error('批量删除失败')
        }
      }
    }
  }
}
</script>

<style scoped>
.executions-page {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
}

.filter-card {
  margin-bottom: 16px;
}

.table-card {
  min-height: 400px;
}

.el-pagination {
  margin-top: 16px;
  text-align: right;
}

.execution-item {
  margin-bottom: 20px;
  padding: 15px;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
}

.execution-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.execution-name {
  font-weight: 600;
  font-size: 16px;
}

.execution-result,
.error-message,
.running-status {
  margin-top: 10px;
}

.execution-gif {
  margin-top: 15px;
}

.execution-gif h4 {
  margin: 0 0 10px 0;
  font-size: 14px;
  color: #606266;
}

.detail-gif {
  margin-top: 20px;
  text-align: center;
}

.detail-gif h3 {
  margin-bottom: 10px;
  font-size: 16px;
  color: #606266;
}

.detail-gif img {
  max-width: 100%;
  border-radius: 4px;
}

.gif-viewer img {
  width: 100%;
}

.final-answer,
.error-message {
  margin-top: 15px;
}

.steps-log-section {
  margin-top: 20px;
}

.steps-log-section h3 {
  margin-bottom: 10px;
  font-size: 16px;
  color: #606266;
}

.steps-log-section .el-collapse {
  border: 1px solid #e4e7ed;
  border-radius: 4px;
}

.steps-log-section .el-collapse-item {
  border-bottom: 1px solid #e4e7ed;
}

.steps-log-section .el-collapse-item:last-child {
  border-bottom: none;
}

.steps-log-section .el-collapse-item__header {
  padding: 12px 20px;
  display: flex;
  align-items: center;
}

.step-number {
  font-weight: bold;
  color: #409EFF;
  margin-right: 8px;
}

.step-abbreviation {
  flex: 1;
  color: #303133;
  font-weight: 500;
}

.step-status-tag {
  margin-left: 12px;
}

.step-detail {
  padding: 15px 20px;
  background-color: #f9fafc;
}

.step-detail .detail-item {
  margin-bottom: 12px;
}

.step-detail .detail-item:last-child {
  margin-bottom: 0;
}

.step-detail .detail-item strong {
  display: block;
  margin-bottom: 4px;
  color: #606266;
  font-size: 13px;
}

.step-detail .detail-item p {
  margin: 0;
  color: #303133;
  line-height: 1.6;
}

.step-detail .detail-item pre {
  margin: 0;
  padding: 10px;
  background-color: #f5f7fa;
  border-radius: 4px;
  font-size: 12px;
  color: #606266;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
