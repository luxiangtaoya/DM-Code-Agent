<template>
  <div class="reports-page">
    <div v-if="!hasCurrentProject" class="empty-state">
      <div class="empty-icon">📊</div>
      <p>请先选择一个项目</p>
      <el-button type="primary" @click="$router.push('/')">去选择项目</el-button>
    </div>

    <div v-else>
      <!-- 筛选条件 -->
      <el-card class="filter-card">
        <div class="filter-header">
          <span class="project-name">{{ currentProject.name }} - 测试报告</span>
          <el-button icon="el-icon-refresh" @click="loadStatistics" :loading="loading">刷新</el-button>
        </div>
        <el-form :inline="true" :model="filters" class="filter-form">
          <el-form-item label="开始日期">
            <el-date-picker
              v-model="filters.startDate"
              type="date"
              placeholder="选择开始日期"
              value-format="yyyy-MM-dd"
              @change="loadStatistics">
            </el-date-picker>
          </el-form-item>
          <el-form-item label="结束日期">
            <el-date-picker
              v-model="filters.endDate"
              type="date"
              placeholder="选择结束日期"
              value-format="yyyy-MM-dd"
              @change="loadStatistics">
            </el-date-picker>
          </el-form-item>
          <el-form-item label="执行状态">
            <el-select v-model="filters.status" placeholder="全部" clearable @change="loadStatistics">
              <el-option label="执行通过" value="执行通过"></el-option>
              <el-option label="执行不通过" value="执行不通过"></el-option>
              <el-option label="执行失败" value="执行失败"></el-option>
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="loadStatistics" icon="el-icon-search">查询</el-button>
          </el-form-item>
        </el-form>
      </el-card>

      <!-- 统计概览 -->
      <el-card class="summary-card">
        <div class="summary-grid">
          <div class="summary-item">
            <div class="summary-icon total">📋</div>
            <div class="summary-info">
              <div class="summary-value">{{ statistics.total || 0 }}</div>
              <div class="summary-label">总用例数</div>
            </div>
          </div>
          <div class="summary-item">
            <div class="summary-icon passed">✅</div>
            <div class="summary-info">
              <div class="summary-value">{{ statistics.passed || 0 }}</div>
              <div class="summary-label">通过</div>
            </div>
          </div>
          <div class="summary-item">
            <div class="summary-icon failed">❌</div>
            <div class="summary-info">
              <div class="summary-value">{{ statistics.failed || 0 }}</div>
              <div class="summary-label">失败</div>
            </div>
          </div>
          <div class="summary-item">
            <div class="summary-icon error">⚠️</div>
            <div class="summary-info">
              <div class="summary-value">{{ statistics.error || 0 }}</div>
              <div class="summary-label">执行错误</div>
            </div>
          </div>
          <div class="summary-item">
            <div class="summary-icon rate">📊</div>
            <div class="summary-info">
              <div class="summary-value">{{ passRate }}%</div>
              <div class="summary-label">通过率</div>
            </div>
          </div>
        </div>
      </el-card>

      <!-- 图表区域 -->
      <el-row :gutter="20">
        <el-col :span="12">
          <el-card class="chart-card">
            <div slot="header">
              <span class="chart-title">状态分布</span>
            </div>
            <div ref="statusChart" class="chart-container"></div>
          </el-card>
        </el-col>
        <el-col :span="12">
          <el-card class="chart-card">
            <div slot="header">
              <span class="chart-title">执行时间分布（秒）</span>
            </div>
            <div ref="timeChart" class="chart-container"></div>
          </el-card>
        </el-col>
      </el-row>

      <el-row :gutter="20" style="margin-top: 20px;">
        <el-col :span="12">
          <el-card class="chart-card">
            <div slot="header">
              <span class="chart-title">步骤数分布</span>
            </div>
            <div ref="stepsChart" class="chart-container"></div>
          </el-card>
        </el-col>
        <el-col :span="12">
          <el-card class="chart-card">
            <div slot="header">
              <span class="chart-title">耗时分布（秒）</span>
            </div>
            <div ref="durationChart" class="chart-container"></div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 缺陷列表 -->
      <el-card class="defects-card" style="margin-top: 20px;">
        <div slot="header">
          <span class="card-title">缺陷列表（执行不通过的用例）</span>
        </div>
        <el-table :data="defects" v-loading="loading" stripe>
          <el-table-column prop="name" label="测试用例" min-width="200" show-overflow-tooltip />
          <el-table-column prop="status" label="状态" width="120">
            <template slot-scope="scope">
              <el-tag :type="getStatusType(scope.row.status)" size="small">
                {{ scope.row.status }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="duration" label="耗时" width="100">
            <template slot-scope="scope">
              {{ formatDuration(scope.row.duration) }}
            </template>
          </el-table-column>
          <el-table-column prop="analysis_count" label="分析次数" width="100" align="center" />
          <el-table-column prop="final_answer" label="执行结果" min-width="250" show-overflow-tooltip />
          <el-table-column label="操作" width="120" fixed="right">
            <template slot-scope="scope">
              <el-button type="primary" size="mini" @click="analyzeDefect(scope.row)">
                🤖 AI分析
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </div>

    <!-- 缺陷分析对话框 -->
    <el-dialog
      title="🤖 AI缺陷分析"
      :visible.sync="showAnalyzeDialog"
      width="700px"
      :close-on-click-modal="false">
      <div v-if="currentDefect" class="analyze-dialog">
        <el-alert
          title="分析说明"
          type="info"
          description="AI将根据测试用例的预期结果和实际执行结果，分析失败原因并提供改进建议"
          :closable="false"
          show-icon
          style="margin-bottom: 20px;">
        </el-alert>

        <el-descriptions :column="1" border>
          <el-descriptions-item label="测试用例">{{ currentDefect.name }}</el-descriptions-item>
          <el-descriptions-item label="执行结果">
            <div class="result-text">{{ currentDefect.final_answer || '无' }}</div>
          </el-descriptions-item>
        </el-descriptions>

        <div v-if="analysisHistory.length > 0" class="analysis-history">
          <h4>历史分析记录</h4>
          <el-timeline>
            <el-timeline-item
              v-for="item in analysisHistory"
              :key="item.id"
              :timestamp="formatTime(item.created_at)">
              <div class="analysis-result">{{ item.analysis_result }}</div>
            </el-timeline-item>
          </el-timeline>
        </div>

        <div v-if="analyzing" class="analyzing-status">
          <el-progress :percentage="100" status="active" :indeterminate="true"></el-progress>
          <p>AI正在分析中，请稍候...</p>
        </div>

        <div v-if="currentAnalysis" class="current-analysis">
          <h4>最新分析结果</h4>
          <div class="analysis-content">{{ currentAnalysis }}</div>
        </div>
      </div>
      <div slot="footer" class="dialog-footer">
        <el-button @click="showAnalyzeDialog = false">关闭</el-button>
        <el-button
          type="primary"
          @click="startAnalyze"
          :loading="analyzing"
          :disabled="analyzing">
          开始分析
        </el-button>
      </div>
    </el-dialog>
  </div>
</template>

<script>
import { mapState, mapGetters } from 'vuex'
import { reportApi } from '@/api'
import * as echarts from 'echarts'

export default {
  name: 'Reports',
  data() {
    return {
      loading: false,
      statistics: {
        total: 0,
        passed: 0,
        failed: 0,
        error: 0
      },
      filters: {
        startDate: '',
        endDate: '',
        status: ''
      },
      defects: [],
      statusChart: null,
      timeChart: null,
      stepsChart: null,
      durationChart: null,
      showAnalyzeDialog: false,
      currentDefect: null,
      analyzing: false,
      currentAnalysis: '',
      analysisHistory: []
    }
  },
  computed: {
    ...mapState(['currentProject']),
    ...mapGetters(['hasCurrentProject']),
    passRate() {
      if (this.statistics.total === 0) return 0
      return ((this.statistics.passed / this.statistics.total) * 100).toFixed(1)
    }
  },
  mounted() {
    if (this.hasCurrentProject) {
      this.loadStatistics()
    }
    this.$nextTick(() => {
      this.initCharts()
    })
    window.addEventListener('resize', this.handleResize)
  },
  beforeDestroy() {
    window.removeEventListener('resize', this.handleResize)
    this.destroyCharts()
  },
  watch: {
    'currentProject.id'() {
      if (this.hasCurrentProject) {
        this.loadStatistics()
      }
    }
  },
  methods: {
    async loadStatistics() {
      if (!this.currentProject?.id) return

      this.loading = true
      try {
        const params = {}
        if (this.filters.startDate) params.start_date = this.filters.startDate
        if (this.filters.endDate) params.end_date = this.filters.endDate
        if (this.filters.status) params.status = this.filters.status

        const response = await reportApi.getStatistics(this.currentProject.id, params)
        const data = response.data

        // 更新统计数据
        this.statistics = data.summary || { total: 0, passed: 0, failed: 0, error: 0 }
        this.defects = data.defects || []

        // 更新图表
        this.updateCharts(data)
      } catch (error) {
        this.$message.error('加载统计数据失败')
      } finally {
        this.loading = false
      }
    },

    initCharts() {
      // 状态分布饼图
      this.statusChart = echarts.init(this.$refs.statusChart)
      // 执行时间分布柱状图
      this.timeChart = echarts.init(this.$refs.timeChart)
      // 步骤数分布柱状图
      this.stepsChart = echarts.init(this.$refs.stepsChart)
      // 耗时分布柱状图
      this.durationChart = echarts.init(this.$refs.durationChart)
    },

    updateCharts(data) {
      // 更新状态分布图
      const statusData = [
        { value: data.summary?.passed || 0, name: '通过', itemStyle: { color: '#67C23A' } },
        { value: data.summary?.failed || 0, name: '失败', itemStyle: { color: '#F56C6C' } },
        { value: data.summary?.error || 0, name: '执行错误', itemStyle: { color: '#E6A23C' } }
      ].filter(item => item.value > 0)

      const statusOption = {
        tooltip: {
          trigger: 'item',
          formatter: '{b}: {c} ({d}%)'
        },
        legend: {
          orient: 'vertical',
          right: 10,
          top: 'center'
        },
        series: [
          {
            name: '状态分布',
            type: 'pie',
            radius: ['40%', '70%'],
            avoidLabelOverlap: false,
            label: {
              show: true,
              formatter: '{b}: {c}\n({d}%)'
            },
            emphasis: {
              label: {
                show: true,
                fontSize: 14,
                fontWeight: 'bold'
              }
            },
            data: statusData
          }
        ]
      }
      this.statusChart.setOption(statusOption, true)

      // 更新执行时间分布图
      const timeStats = data.execution_time_stats || {}
      const timeData = []
      const timeLabels = ['0-10s', '10-30s', '30-60s', '60-120s', '120-180s', '180-300s', '300-600s', '600s+']
      timeLabels.forEach(label => {
        if (timeStats[label] > 0) {
          timeData.push({ name: label, value: timeStats[label] })
        }
      })

      const timeOption = {
        tooltip: {
          trigger: 'axis',
          axisPointer: {
            type: 'shadow'
          },
          formatter: '{b}: {c}个用例'
        },
        grid: {
          left: '3%',
          right: '4%',
          bottom: '3%',
          containLabel: true
        },
        xAxis: {
          type: 'category',
          data: timeData.map(item => item.name),
          axisLabel: {
            rotate: 30
          }
        },
        yAxis: {
          type: 'value',
          name: '用例数量',
          nameTextStyle: {
            padding: [0, 0, 0, 20]
          }
        },
        series: [
          {
            name: '执行耗时',
            type: 'bar',
            data: timeData.map(item => item.value),
            itemStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: '#83bff6' },
                { offset: 0.5, color: '#188df0' },
                { offset: 1, color: '#188df0' }
              ])
            }
          }
        ]
      }
      this.timeChart.setOption(timeOption, true)

      // 更新步骤数分布图
      const stepStats = data.step_count_stats || {}
      const stepData = []
      const stepLabels = ['1-3步', '4-6步', '7-10步', '11-15步', '16-20步', '21-30步', '30步+']
      stepLabels.forEach(label => {
        if (stepStats[label] > 0) {
          stepData.push({ name: label, value: stepStats[label] })
        }
      })

      const stepOption = {
        tooltip: {
          trigger: 'axis',
          axisPointer: {
            type: 'shadow'
          },
          formatter: '{b}: {c}个用例'
        },
        grid: {
          left: '3%',
          right: '4%',
          bottom: '3%',
          containLabel: true
        },
        xAxis: {
          type: 'category',
          data: stepData.map(item => item.name),
          axisLabel: {
            rotate: 30
          }
        },
        yAxis: {
          type: 'value',
          name: '用例数量',
          nameTextStyle: {
            padding: [0, 0, 0, 20]
          }
        },
        series: [
          {
            name: '步骤数',
            type: 'bar',
            data: stepData.map(item => item.value),
            itemStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: '#90ee7e' },
                { offset: 0.5, color: '#5db874' },
                { offset: 1, color: '#5db874' }
              ])
            }
          }
        ]
      }
      this.stepsChart.setOption(stepOption, true)

      // 更新耗时分布图
      const durationStats = data.duration_stats || {}
      const durationData = []
      const durationLabels = ['0-10s', '10-30s', '30-60s', '60-120s', '120-180s', '180-300s', '300-600s', '600s+']
      durationLabels.forEach(label => {
        if (durationStats[label] > 0) {
          durationData.push({ name: label, value: durationStats[label] })
        }
      })

      const durationOption = {
        tooltip: {
          trigger: 'axis',
          axisPointer: {
            type: 'shadow'
          },
          formatter: '{b}: {c}个用例'
        },
        grid: {
          left: '3%',
          right: '4%',
          bottom: '3%',
          containLabel: true
        },
        xAxis: {
          type: 'category',
          data: durationData.map(item => item.name),
          axisLabel: {
            rotate: 30
          }
        },
        yAxis: {
          type: 'value',
          name: '用例数量',
          nameTextStyle: {
            padding: [0, 0, 0, 20]
          }
        },
        series: [
          {
            name: '执行耗时',
            type: 'bar',
            data: durationData.map(item => item.value),
            itemStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: '#f0ad4e' },
                { offset: 0.5, color: '#ec971f' },
                { offset: 1, color: '#ec971f' }
              ])
            }
          }
        ]
      }
      this.durationChart.setOption(durationOption, true)
    },

    handleResize() {
      if (this.statusChart) this.statusChart.resize()
      if (this.timeChart) this.timeChart.resize()
      if (this.stepsChart) this.stepsChart.resize()
      if (this.durationChart) this.durationChart.resize()
    },

    destroyCharts() {
      if (this.statusChart) {
        this.statusChart.dispose()
        this.statusChart = null
      }
      if (this.timeChart) {
        this.timeChart.dispose()
        this.timeChart = null
      }
      if (this.stepsChart) {
        this.stepsChart.dispose()
        this.stepsChart = null
      }
      if (this.durationChart) {
        this.durationChart.dispose()
        this.durationChart = null
      }
    },

    async analyzeDefect(row) {
      this.currentDefect = row
      this.currentAnalysis = ''
      this.analysisHistory = []
      this.showAnalyzeDialog = true

      // 加载历史分析记录
      try {
        const response = await reportApi.getDefectAnalyses(row.testcase_id)
        this.analysisHistory = response.data.analyses || []
      } catch (error) {
        console.error('加载分析历史失败:', error)
      }
    },

    async startAnalyze() {
      if (!this.currentDefect) return

      this.analyzing = true
      this.currentAnalysis = ''

      try {
        const response = await reportApi.analyzeDefect(
          this.currentDefect.testcase_id,
          { execution_id: this.currentDefect.execution_id }
        )

        this.currentAnalysis = response.data.analysis_result || '分析完成'

        // 重新加载历史记录
        const historyResponse = await reportApi.getDefectAnalyses(this.currentDefect.testcase_id)
        this.analysisHistory = historyResponse.data.analyses || []

        this.$message.success('缺陷分析完成')
      } catch (error) {
        this.$message.error('缺陷分析失败')
      } finally {
        this.analyzing = false
      }
    },

    getStatusType(status) {
      const map = {
        '执行通过': 'success',
        '执行不通过': 'danger',
        '执行失败': 'warning'
      }
      return map[status] || 'info'
    },

    formatDuration(seconds) {
      if (!seconds || seconds < 0) return '-'
      if (seconds < 60) return `${seconds}秒`
      const minutes = Math.floor(seconds / 60)
      const remainingSeconds = seconds % 60
      if (remainingSeconds === 0) return `${minutes}分`
      return `${minutes}分${remainingSeconds}秒`
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
    }
  }
}
</script>

<style scoped>
.reports-page {
  max-width: 1600px;
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

.filter-card {
  margin-bottom: 20px;
}

.filter-header {
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

.summary-card {
  margin-bottom: 20px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 20px;
}

.summary-item {
  display: flex;
  align-items: center;
  padding: 15px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 8px;
  color: white;
}

.summary-item:nth-child(2) {
  background: linear-gradient(135deg, #84fab0 0%, #8fd3f4 100%);
}

.summary-item:nth-child(3) {
  background: linear-gradient(135deg, #fa709a 0%, #fee140 100%);
}

.summary-item:nth-child(4) {
  background: linear-gradient(135deg, #ff9a9e 0%, #fecfef 100%);
}

.summary-item:nth-child(5) {
  background: linear-gradient(135deg, #a18cd1 0%, #fbc2eb 100%);
}

.summary-icon {
  font-size: 40px;
  margin-right: 15px;
}

.summary-info {
  flex: 1;
}

.summary-value {
  font-size: 32px;
  font-weight: bold;
  line-height: 1.2;
}

.summary-label {
  font-size: 14px;
  opacity: 0.9;
  margin-top: 5px;
}

.chart-card {
  margin-bottom: 20px;
}

.chart-title {
  font-size: 16px;
  font-weight: 600;
  color: #333;
}

.chart-container {
  height: 300px;
}

.defects-card {
  margin-bottom: 20px;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
  color: #333;
}

.analyze-dialog {
  max-height: 600px;
  overflow-y: auto;
}

.result-text {
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.6;
  color: #606266;
}

.analysis-history {
  margin-top: 20px;
  padding: 15px;
  background: #f5f7fa;
  border-radius: 4px;
}

.analysis-history h4 {
  margin: 0 0 15px 0;
  font-size: 14px;
  color: #303133;
}

.analysis-result {
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.6;
  color: #606266;
}

.analyzing-status {
  text-align: center;
  padding: 30px;
}

.analyzing-status p {
  margin-top: 15px;
  color: #909399;
}

.current-analysis {
  margin-top: 20px;
  padding: 15px;
  background: #f0f9ff;
  border: 1px solid #d9ecff;
  border-radius: 4px;
}

.current-analysis h4 {
  margin: 0 0 10px 0;
  font-size: 14px;
  color: #303133;
}

.analysis-content {
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.6;
  color: #606266;
}
</style>