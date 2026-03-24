<template>
  <div class="testcases-page">
    <div v-if="!hasCurrentProject" class="empty-state">
      <div class="empty-icon">📝</div>
      <p>请先选择一个项目</p>
      <el-button type="primary" @click="$router.push('/')">去选择项目</el-button>
    </div>

    <div v-else>
      <!-- 操作栏 -->
      <el-card class="action-bar">
        <div class="action-header">
          <span class="project-name">{{ currentProject.name }} - 测试用例</span>
          <div class="action-buttons">
            <el-button icon="el-icon-download" @click="downloadTemplate">📥 下载模板</el-button>
            <el-button icon="el-icon-upload2" @click="showExcelUploadDialog = true">📤 Excel导入</el-button>
            <el-button type="primary" icon="el-icon-plus" @click="showCreateDialog = true">✏️ 新建用例</el-button>
          </div>
        </div>

        <!-- 筛选和搜索 -->
        <el-form inline>
          <el-form-item label="优先级">
            <el-select v-model="filters.priority" placeholder="全部" clearable @change="loadTestCases">
              <el-option label="P0" value="P0"></el-option>
              <el-option label="P1" value="P1"></el-option>
              <el-option label="P2" value="P2"></el-option>
              <el-option label="P3" value="P3"></el-option>
            </el-select>
          </el-form-item>
          <el-form-item label="用例类型">
            <el-select v-model="filters.caseType" placeholder="全部" clearable @change="loadTestCases">
              <el-option label="正向" value="正向"></el-option>
              <el-option label="负向" value="负向"></el-option>
              <el-option label="边界" value="边界"></el-option>
              <el-option label="性能" value="性能"></el-option>
              <el-option label="安全" value="安全"></el-option>
            </el-select>
          </el-form-item>
          <el-form-item label="状态">
            <el-select v-model="filters.status" placeholder="全部" clearable @change="loadTestCases">
              <el-option label="待测试" value="待测试"></el-option>
              <el-option label="执行通过" value="执行通过"></el-option>
              <el-option label="执行不通过" value="执行不通过"></el-option>
              <el-option label="执行失败" value="执行失败"></el-option>
            </el-select>
          </el-form-item>
          <el-form-item label="搜索">
            <el-input
              v-model="filters.keyword"
              placeholder="搜索用例名称"
              style="width: 200px;"
              @keyup.enter.native="loadTestCases"
            />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="loadTestCases">搜索</el-button>
          </el-form-item>
        </el-form>
      </el-card>

      <!-- 用例列表 -->
      <el-card>
        <el-table
          ref="testCaseTable"
          :data="testCases"
          v-loading="loading"
          @selection-change="handleSelectionChange"
        >
          <el-table-column type="selection" width="55" />
          <el-table-column prop="name" label="用例名称" width="150" show-overflow-tooltip />
          <el-table-column prop="description" label="用例描述" width="200" show-overflow-tooltip />
          <el-table-column label="优先级" width="80">
            <template slot-scope="scope">
              <el-tag :type="priorityType(scope.row.priority)" size="small">
                {{ scope.row.priority }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="类型" width="80">
            <template slot-scope="scope">
              <el-tag size="small" :type="caseTypeColor(scope.row.case_type)">
                {{ scope.row.case_type }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="100">
            <template slot-scope="scope">
              <el-tag size="small" :type="statusType(scope.row.status)">
                {{ scope.row.status }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="tester" label="测试人员" width="100" />
          <el-table-column prop="test_date" label="测试日期" width="110" />
          <el-table-column label="操作" width="450" fixed="right">
            <template slot-scope="scope">
              <el-button size="mini" @click="viewTestCase(scope.row)">查看</el-button>
              <el-button size="mini" type="primary" @click="editTestCase(scope.row)">编辑</el-button>
              <el-button size="mini" type="success" @click="quickExecute(scope.row)">🤖 执行</el-button>
              <el-button size="mini" type="info" @click="viewLatestExecution(scope.row)" :disabled="!hasExecution(scope.row)">📊 结果</el-button>
              <el-button size="mini" type="danger" @click="deleteTestCase(scope.row.id)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>

        <!-- 批量操作 -->
        <div class="batch-actions" v-if="selectedCases.length > 0">
          <span>已选择 {{ selectedCases.length }} 条</span>
          <div class="batch-buttons">
            <el-button size="small" type="success" icon="el-icon-video-play" @click="showExecuteDialog = true">
              🤖 AI自动化执行
            </el-button>
            <el-button size="small" type="danger" @click="batchDelete">批量删除</el-button>
          </div>
        </div>

        <!-- 分页 -->
        <el-pagination
          v-if="pagination.total > 0"
          class="pagination"
          :current-page="pagination.page"
          :page-size="pagination.pageSize"
          :total="pagination.total"
          @current-change="handlePageChange"
          layout="total, prev, pager, next"
        />
      </el-card>
    </div>

    <!-- Excel导入对话框 -->
    <el-dialog title="Excel导入测试用例" :visible.sync="showExcelUploadDialog" width="500px">
      <el-upload
        ref="excelUpload"
        :auto-upload="false"
        :limit="1"
        :on-change="handleExcelChange"
        :on-exceed="handleExceed"
        accept=".xlsx,.xls"
        drag
        action="#"
      >
        <i class="el-icon-upload"></i>
        <div class="el-upload__text">将文件拖到此处，或<em>点击上传</em></div>
        <div class="el-upload__tip" slot="tip">只支持 .xlsx 或 .xls 格式的Excel文件</div>
      </el-upload>
      <div slot="footer" class="dialog-footer">
        <el-button @click="showExcelUploadDialog = false">取消</el-button>
        <el-button type="primary" @click="importExcel" :loading="importing">导入</el-button>
      </div>
    </el-dialog>

    <!-- 新建/编辑测试用例对话框 -->
    <el-dialog
      :title="isEdit ? '编辑测试用例' : '新建测试用例'"
      :visible.sync="showCreateDialog"
      width="800px"
      :close-on-click-modal="false"
    >
      <el-form :model="testCaseForm" :rules="formRules" ref="testCaseForm" label-width="100px">
        <el-form-item label="用例名称" prop="name">
          <el-input v-model="testCaseForm.name" placeholder="示例：我的账户-账户展示-001" />
        </el-form-item>

        <el-form-item label="用例描述" prop="description">
          <el-input
            v-model="testCaseForm.description"
            type="textarea"
            :rows="2"
            placeholder="简要描述测试用例的目的"
          />
        </el-form-item>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="用例优先级" prop="priority">
              <el-select v-model="testCaseForm.priority" placeholder="请选择">
                <el-option label="P0 - 高" value="P0"></el-option>
                <el-option label="P1 - 中" value="P1"></el-option>
                <el-option label="P2 - 低" value="P2"></el-option>
                <el-option label="P3" value="P3"></el-option>
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="用例类型" prop="case_type">
              <el-select v-model="testCaseForm.case_type" placeholder="请选择">
                <el-option label="正向" value="正向"></el-option>
                <el-option label="负向" value="负向"></el-option>
                <el-option label="边界" value="边界"></el-option>
                <el-option label="性能" value="性能"></el-option>
                <el-option label="安全" value="安全"></el-option>
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="前置条件" prop="precondition">
          <el-input
            v-model="testCaseForm.precondition"
            type="textarea"
            :rows="3"
            placeholder="示例：&#10;1. 用户已注册并登录&#10;2. 用户已添加至少一张借记卡"
          />
        </el-form-item>

        <el-form-item label="测试步骤" prop="steps">
          <el-input
            v-model="testCaseForm.steps"
            type="textarea"
            :rows="5"
            placeholder="示例：&#10;1. 打开浏览器，访问系统首页 http://localhost:8081&#10;2. 点击 [首页].功能卡片.我的账户卡片&#10;3. 等待页面跳转完成&#10;4. 检查 [我的账户页面].借记卡区域.卡片列表 的显示内容"
          />
        </el-form-item>

        <el-form-item label="预期结果" prop="expected_result">
          <el-input
            v-model="testCaseForm.expected_result"
            type="textarea"
            :rows="4"
            placeholder="示例：&#10;1. 页面跳转到 /accounts 路由&#10;2. 页面标题显示 &quot;我的账户&quot;&#10;3. 借记卡区域显示所有借记卡卡片"
          />
        </el-form-item>

        <el-form-item label="实际结果">
          <el-input
            v-model="testCaseForm.actual_result"
            type="textarea"
            :rows="3"
            placeholder="测试执行后的实际结果"
          />
        </el-form-item>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="测试状态" prop="status">
              <el-select v-model="testCaseForm.status" placeholder="请选择">
                <el-option label="待测试" value="待测试"></el-option>
                <el-option label="执行通过" value="执行通过"></el-option>
                <el-option label="执行不通过" value="执行不通过"></el-option>
                <el-option label="执行失败" value="执行失败"></el-option>
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="测试人员">
              <el-input v-model="testCaseForm.tester" placeholder="测试人员姓名" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="测试日期">
          <el-date-picker
            v-model="testCaseForm.test_date"
            type="date"
            placeholder="选择日期"
            value-format="yyyy-MM-dd"
            style="width: 200px;"
          />
        </el-form-item>
      </el-form>
      <div slot="footer" class="dialog-footer">
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="saveTestCase" :loading="saving">保存</el-button>
      </div>
    </el-dialog>

    <!-- 查看测试用例对话框 -->
    <el-dialog title="测试用例详情" :visible.sync="showViewDialog" width="700px">
      <div class="case-detail" v-if="viewingCase">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="用例名称" :span="2">{{ viewingCase.name }}</el-descriptions-item>
          <el-descriptions-item label="用例描述" :span="2">{{ viewingCase.description || '无' }}</el-descriptions-item>
          <el-descriptions-item label="优先级">
            <el-tag :type="priorityType(viewingCase.priority)">{{ viewingCase.priority }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="用例类型">
            <el-tag :type="caseTypeColor(viewingCase.case_type)">{{ viewingCase.case_type }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="测试状态" :span="2">
            <el-tag :type="statusType(viewingCase.status)">{{ viewingCase.status }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="前置条件" :span="2">
            <pre class="whitespace-pre-wrap">{{ viewingCase.precondition || '无' }}</pre>
          </el-descriptions-item>
          <el-descriptions-item label="测试步骤" :span="2">
            <pre class="whitespace-pre-wrap">{{ viewingCase.steps }}</pre>
          </el-descriptions-item>
          <el-descriptions-item label="预期结果" :span="2">
            <pre class="whitespace-pre-wrap">{{ viewingCase.expected_result }}</pre>
          </el-descriptions-item>
          <el-descriptions-item label="实际结果" :span="2" v-if="viewingCase.actual_result">
            <pre class="whitespace-pre-wrap">{{ viewingCase.actual_result }}</pre>
          </el-descriptions-item>
          <el-descriptions-item label="测试人员">{{ viewingCase.tester || '未指定' }}</el-descriptions-item>
          <el-descriptions-item label="测试日期">{{ viewingCase.test_date || '未设置' }}</el-descriptions-item>
        </el-descriptions>
      </div>
      <div slot="footer" class="dialog-footer">
        <el-button @click="showViewDialog = false">关闭</el-button>
        <el-button type="primary" @click="editTestCase(viewingCase)">编辑</el-button>
      </div>
    </el-dialog>

    <!-- AI自动化执行配置对话框 -->
    <el-dialog title="🤖 AI自动化执行" :visible.sync="showExecuteDialog" width="600px">
      <el-alert
        title="执行说明"
        type="info"
        :description="`将执行选中的 ${selectedCases.length} 条测试用例，执行过程中将在执行记录页面实时显示进度`"
        :closable="false"
        show-icon
        style="margin-bottom: 20px;">
      </el-alert>

      <el-form :model="executeConfig" label-width="100px">
        <el-form-item label="AI模型">
          <el-input v-model="executeConfig.model" placeholder="例如: qwen3.5-flash">
            <template slot="prepend">
              <i class="el-icon-cpu"></i>
            </template>
          </el-input>
          <div class="form-tip">常用模型: qwen3.5-flash, qwen-turbo, qwen-plus</div>
        </el-form-item>

        <el-form-item label="提供商">
          <el-select v-model="executeConfig.provider" placeholder="选择提供商" style="width: 100%">
            <el-option label="Qwen (通义千问)" value="qwen">
              <span>🌟 Qwen</span>
              <span style="color: #8492a6; font-size: 12px; margin-left: 10px">通义千问</span>
            </el-option>
            <el-option label="OpenAI" value="openai">
              <span>🤖 OpenAI</span>
              <span style="color: #8492a6; font-size: 12px; margin-left: 10px">GPT系列</span>
            </el-option>
            <el-option label="Claude" value="claude">
              <span>🧠 Claude</span>
              <span style="color: #8492a6; font-size: 12px; margin-left: 10px">Anthropic</span>
            </el-option>
          </el-select>
        </el-form-item>

        <el-form-item label="执行选项">
          <el-checkbox v-model="executeConfig.enableScreenshots">启用截图（生成执行GIF）</el-checkbox>
        </el-form-item>

        <el-divider></el-divider>

        <div class="selected-cases-summary">
          <h4>待执行的测试用例:</h4>
          <el-tag
            v-for="item in selectedCases"
            :key="item.id"
            closable
            @close="removeFromSelection(item.id)"
            style="margin: 5px;">
            {{ item.name }}
          </el-tag>
        </div>
      </el-form>

      <div slot="footer" class="dialog-footer">
        <el-button @click="showExecuteDialog = false">取消</el-button>
        <el-button type="primary" @click="startExecution" :loading="executing">
          <i class="el-icon-video-play"></i> 开始执行
        </el-button>
      </div>
    </el-dialog>

    <!-- 执行结果查看对话框 -->
    <el-dialog title="执行结果" :visible.sync="showExecutionResultDialog" width="900px">
      <div v-if="viewingLatestExecution" class="execution-detail">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="状态">
            <el-tag :type="getExecutionStatusType(viewingLatestExecution.status)" size="small">
              {{ getExecutionStatusText(viewingLatestExecution.status, viewingLatestExecution.result) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="结果">
            <el-tag v-if="viewingLatestExecution.result" :type="viewingLatestExecution.result === 'passed' ? 'success' : 'danger'" size="small">
              {{ viewingLatestExecution.result === 'passed' ? '通过' : '未通过' }}
            </el-tag>
            <span v-else>-</span>
          </el-descriptions-item>
          <el-descriptions-item label="模型">{{ viewingLatestExecution.model }}</el-descriptions-item>
          <el-descriptions-item label="提供商">{{ viewingLatestExecution.provider }}</el-descriptions-item>
          <el-descriptions-item label="执行时间">{{ formatExecutionTime(viewingLatestExecution.end_time || viewingLatestExecution.created_at) }}</el-descriptions-item>
          <el-descriptions-item label="耗时">{{ formatExecutionDuration(viewingLatestExecution.duration) }}</el-descriptions-item>
        </el-descriptions>

        <div v-if="viewingLatestExecution.steps_log && viewingLatestExecution.steps_log.length > 0" class="steps-log-section">
          <h3>执行步骤:</h3>
          <el-collapse v-model="activeSteps">
            <el-collapse-item
              v-for="(step, index) in viewingLatestExecution.steps_log"
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

        <div v-if="viewingLatestExecution.gif_path" class="detail-gif">
          <h3>执行 GIF:</h3>
          <img :src="getExecutionGif(viewingLatestExecution.gif_path)" alt="execution gif" />
        </div>

        <div v-if="viewingLatestExecution.error_message" class="error-message">
          <el-alert
            type="error"
            title="错误信息"
            :description="viewingLatestExecution.error_message"
            :closable="false"
            show-icon>
          </el-alert>
        </div>

        <div v-if="viewingLatestExecution.final_answer" class="final-answer">
          <el-alert
            :type="viewingLatestExecution.result === 'passed' ? 'success' : 'error'"
            :title="viewingLatestExecution.result === 'passed' ? '测试通过' : '测试失败'"
            :description="viewingLatestExecution.final_answer"
            :closable="false"
            show-icon>
          </el-alert>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script>
import { testCaseApi } from '@/api'
import { mapState, mapGetters } from 'vuex'

export default {
  name: 'TestCases',
  data() {
    return {
      loading: false,
      saving: false,
      importing: false,
      executing: false,
      testCases: [],
      selectedCases: [],
      filters: {
        priority: '',
        caseType: '',
        status: '',
        keyword: ''
      },
      pagination: {
        page: 1,
        pageSize: 20,
        total: 0
      },
      showUploadDialog: false,
      showCreateDialog: false,
      showViewDialog: false,
      showExcelUploadDialog: false,
      showExecuteDialog: false,
      showExecutionResultDialog: false,
      isEdit: false,
      editingId: null,
      viewingCase: null,
      viewingLatestExecution: null,
      activeSteps: [],
      testCaseForm: {
        name: '',
        description: '',
        priority: 'P1',
        case_type: '正向',
        precondition: '',
        steps: '',
        expected_result: '',
        actual_result: '',
        status: '待测试',
        tester: '',
        test_date: ''
      },
      executeConfig: {
        model: 'qwen3.5-flash',
        provider: 'qwen',
        enableScreenshots: true
      },
      formRules: {
        name: [{ required: true, message: '请输入用例名称', trigger: 'blur' }],
        steps: [{ required: true, message: '请输入测试步骤', trigger: 'blur' }],
        expected_result: [{ required: true, message: '请输入预期结果', trigger: 'blur' }]
      },
      excelFile: null
    }
  },
  computed: {
    ...mapState(['currentProject']),
    ...mapGetters(['hasCurrentProject'])
  },
  mounted() {
    if (this.hasCurrentProject) {
      this.loadTestCases()
    }
  },
  watch: {
    'currentProject.id'() {
      if (this.hasCurrentProject) {
        this.loadTestCases()
      }
    }
  },
  methods: {
    async loadTestCases() {
      if (!this.currentProject?.id) return

      this.loading = true
      try {
        const params = {
          page: this.pagination.page,
          page_size: this.pagination.pageSize
        }
        if (this.filters.priority) params.priority = this.filters.priority
        if (this.filters.caseType) params.case_type = this.filters.caseType
        if (this.filters.status) params.status = this.filters.status
        if (this.filters.keyword) params.keyword = this.filters.keyword

        const res = await testCaseApi.getList(this.currentProject.id, params)
        this.testCases = res.data.items || []
        this.pagination.total = res.data.total || 0
      } catch (error) {
        // 错误已由拦截器处理
      } finally {
        this.loading = false
      }
    },

    handlePageChange(page) {
      this.pagination.page = page
      this.loadTestCases()
    },

    handleSelectionChange(selection) {
      this.selectedCases = selection
    },

    resetForm() {
      this.testCaseForm = {
        name: '',
        description: '',
        priority: 'P1',
        case_type: '正向',
        precondition: '',
        steps: '',
        expected_result: '',
        actual_result: '',
        status: '待测试',
        tester: '',
        test_date: ''
      }
      this.isEdit = false
      this.editingId = null
      if (this.$refs.testCaseForm) {
        this.$refs.testCaseForm.clearValidate()
      }
    },

    async saveTestCase() {
      this.$refs.testCaseForm.validate(async (valid) => {
        if (!valid) return

        this.saving = true
        try {
          if (this.isEdit) {
            await testCaseApi.update(this.editingId, this.testCaseForm)
            this.$message.success('更新成功')
          } else {
            await testCaseApi.create(this.currentProject.id, this.testCaseForm)
            this.$message.success('创建成功')
          }
          this.showCreateDialog = false
          this.resetForm()
          this.loadTestCases()
        } catch (error) {
          // 错误已由拦截器处理
        } finally {
          this.saving = false
        }
      })
    },

    editTestCase(row) {
      this.showViewDialog = false
      this.isEdit = true
      this.editingId = row.id
      this.testCaseForm = {
        name: row.name,
        description: row.description || '',
        priority: row.priority,
        case_type: row.case_type || '正向',
        precondition: row.precondition || '',
        steps: Array.isArray(row.steps) ? row.steps.join('\n') : row.steps,
        expected_result: row.expected_result,
        actual_result: row.actual_result || '',
        status: row.status,
        tester: row.tester || '',
        test_date: row.test_date || ''
      }
      this.showCreateDialog = true
    },

    viewTestCase(row) {
      this.viewingCase = row
      this.showViewDialog = true
    },

    async deleteTestCase(id) {
      await this.$confirm('确定要删除这条测试用例吗？', '提示', {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      })

      try {
        await testCaseApi.delete(id)
        this.$message.success('删除成功')
        this.loadTestCases()
      } catch (error) {
        if (error !== 'cancel') {
          // 错误已由拦截器处理
        }
      }
    },

    async batchDelete() {
      await this.$confirm(`确定要删除选中的 ${this.selectedCases.length} 条测试用例吗？`, '提示', {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      })

      try {
        await testCaseApi.batchDelete(this.selectedCases.map(c => c.id))
        this.$message.success('删除成功')
        this.selectedCases = []
        this.loadTestCases()
      } catch (error) {
        if (error !== 'cancel') {
          // 错误已由拦截器处理
        }
      }
    },

    handleExcelChange(file) {
      this.excelFile = file.raw
    },

    handleExceed() {
      this.$message.warning('只能上传一个文件')
    },

    async importExcel() {
      if (!this.excelFile) {
        this.$message.warning('请选择要导入的Excel文件')
        return
      }

      this.importing = true
      try {
        const formData = new FormData()
        formData.append('file', this.excelFile)

        await testCaseApi.importExcel(this.currentProject.id, formData)
        this.$message.success('导入成功')
        this.showExcelUploadDialog = false
        this.excelFile = null
        if (this.$refs.excelUpload) {
          this.$refs.excelUpload.clearFiles()
        }
        this.loadTestCases()
      } catch (error) {
        // 错误已由拦截器处理
      } finally {
        this.importing = false
      }
    },

    downloadTemplate() {
      window.open(`${process.env.VUE_APP_API_BASE_URL || 'http://localhost:8000/api/v1'}/testcases/export/template`, '_blank')
    },

    priorityType(priority) {
      const map = { 'P0': 'danger', 'P1': 'warning', 'P2': 'info', 'P3': '' }
      return map[priority] || ''
    },

    caseTypeColor(type) {
      const map = { '正向': 'success', '负向': 'warning', '边界': 'info', '性能': 'danger', '安全': '' }
      return map[type] || ''
    },

    statusType(status) {
      // 统一状态定义和颜色
      const map = {
        '待测试': 'info',
        '执行通过': 'success',
        '执行不通过': 'danger',
        '执行失败': 'warning'
      }
      return map[status] || 'info'
    },

    removeFromSelection(caseId) {
      this.selectedCases = this.selectedCases.filter(c => c.id !== caseId)
      // 同时在表格中取消选中
      const table = this.$refs.testCaseTable
      if (table) {
        const row = this.testCases.find(tc => tc.id === caseId)
        if (row) {
          table.toggleRowSelection(row, false)
        }
      }
    },

    async quickExecute(testCase) {
      // 快速执行单个测试用例，先打开配置对话框
      this.selectedCases = [testCase]
      this.showExecuteDialog = true
    },

    hasExecution(testCase) {
      // 检查测试用例是否有执行记录
      return testCase.status !== '待测试'
    },

    async viewLatestExecution(testCase) {
      // 查看最新执行结果
      try {
        const response = await testCaseApi.getLatestExecution(testCase.id)
        if (response.data) {
          this.viewingLatestExecution = response.data
          this.showExecutionResultDialog = true
        } else {
          this.$message.info('该测试用例暂无执行记录')
        }
      } catch (error) {
        this.$message.error('加载执行结果失败')
      }
    },

    async startExecution() {
      if (this.selectedCases.length === 0) {
        this.$message.warning('请先选择要执行的测试用例')
        return
      }

      this.executing = true
      try {
        // 批量执行
        const testcaseIds = this.selectedCases.map(tc => tc.id)
        await testCaseApi.batchExecute(testcaseIds, {
          model: this.executeConfig.model,
          provider: this.executeConfig.provider,
          enable_screenshots: this.executeConfig.enableScreenshots
        })

        // 关闭对话框，跳转到执行记录页面
        const count = testcaseIds.length
        this.showExecuteDialog = false
        this.selectedCases = []
        this.$message.success(`已启动 ${count} 条测试用例的执行，即将跳转到执行记录页面`)

        // 跳转到执行记录页面
        setTimeout(() => {
          this.$router.push('/executions')
        }, 500)
      } catch (error) {
        this.$message.error('启动执行失败')
      } finally {
        this.executing = false
      }
    },

    // 执行状态类型
    getExecutionStatusType(status) {
      const typeMap = {
        pending: 'info',
        running: 'warning',
        completed: 'success',
        failed: 'danger'
      }
      return typeMap[status] || 'info'
    },

    // 执行状态文本
    getExecutionStatusText(status, result) {
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

    // 格式化执行时间
    formatExecutionTime(time) {
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

    // 格式化执行时长
    formatExecutionDuration(seconds) {
      if (!seconds || seconds < 0) return '-'
      if (seconds < 60) return `${seconds}秒`
      const minutes = Math.floor(seconds / 60)
      const remainingSeconds = seconds % 60
      if (remainingSeconds === 0) return `${minutes}分`
      return `${minutes}分${remainingSeconds}秒`
    },

    // 获取执行GIF路径
    getExecutionGif(path) {
      if (!path) return ''
      // 如果是相对路径（如 /screenshots/xxx/task_animation.gif），直接返回
      if (path.startsWith('/')) {
        return path
      }
      // 如果是相对路径但没有开头 /，添加 /
      if (path.startsWith('screenshots')) {
        return '/' + path
      }
      // 如果已经是完整URL，直接返回
      if (path.startsWith('http://') || path.startsWith('https://')) {
        return path
      }
      return ''
    },

    // 格式化动作输入
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
    }
  }
}
</script>

<style scoped>
.testcases-page {
  max-width: 1600px;
}

.action-bar {
  margin-bottom: 20px;
}

.action-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.project-name {
  font-size: 18px;
  font-weight: 600;
  color: #333;
}

.action-buttons {
  display: flex;
  gap: 10px;
}

.batch-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 16px;
  padding: 12px;
  background: #f5f7fa;
  border-radius: 4px;
}

.batch-buttons {
  display: flex;
  gap: 10px;
}

.selected-cases-summary {
  max-height: 200px;
  overflow-y: auto;
}

.selected-cases-summary h4 {
  margin: 0 0 10px 0;
  font-size: 14px;
  color: #606266;
}

.form-tip {
  font-size: 12px;
  color: #909399;
  margin-top: 5px;
}

.pagination {
  margin-top: 20px;
  text-align: right;
}

.empty-state {
  text-align: center;
  padding: 100px 20px;
}

.empty-icon {
  font-size: 64px;
  margin-bottom: 20px;
  opacity: 0.5;
}

.case-detail {
  font-size: 14px;
}

.whitespace-pre-wrap {
  white-space: pre-wrap;
  word-break: break-word;
  font-family: inherit;
  margin: 0;
}

/* 执行结果相关样式 */
.execution-detail {
  font-size: 14px;
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

.final-answer,
.error-message {
  margin-top: 15px;
}
</style>
