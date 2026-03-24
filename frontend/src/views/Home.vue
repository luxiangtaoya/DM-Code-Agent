<template>
  <div class="home-page">
    <!-- 创建项目 -->
    <el-card class="create-project-card">
      <div slot="header">
        <span class="card-title">创建新项目</span>
      </div>
      <el-form inline @submit.native.prevent="createProject">
        <el-form-item label="项目名称">
          <el-input
            v-model="newProject.name"
            placeholder="请输入项目名称"
            style="width: 300px;"
          />
        </el-form-item>
        <el-form-item label="项目描述">
          <el-input
            v-model="newProject.description"
            placeholder="请输入项目描述（可选）"
            style="width: 400px;"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" native-type="submit" :loading="creating">
            创建项目
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 项目列表 -->
    <el-card>
      <div slot="header">
        <span class="card-title">我的项目</span>
      </div>
      <el-row :gutter="20" v-loading="loading">
        <el-col :span="8" v-for="project in projects" :key="project.id">
          <div class="project-card" @click="selectProject(project)">
            <div class="project-name">{{ project.name }}</div>
            <div class="project-desc">{{ project.description || '暂无描述' }}</div>
            <div class="project-meta">
              <span>📝 {{ project.test_case_count }} 个用例</span>
              <span>🚀 {{ project.execution_count }} 次执行</span>
              <span>📅 {{ formatDate(project.created_at) }}</span>
            </div>
          </div>
        </el-col>
      </el-row>
      <div class="empty-state" v-if="!loading && projects.length === 0">
        <div class="empty-icon">📁</div>
        <p>还没有项目，创建一个开始吧！</p>
      </div>
    </el-card>
  </div>
</template>

<script>
import { projectApi } from '@/api'
import { mapState, mapActions } from 'vuex'

export default {
  name: 'Home',
  data() {
    return {
      newProject: {
        name: '',
        description: ''
      },
      creating: false,
      loading: false
    }
  },
  computed: {
    ...mapState(['projects'])
  },
  mounted() {
    this.loadProjects()
  },
  methods: {
    ...mapActions(['selectProject']),

    async loadProjects() {
      this.loading = true
      try {
        const res = await projectApi.getList()
        this.$store.commit('SET_PROJECTS', res.data || [])
      } catch (error) {
        // 错误已由拦截器处理
      } finally {
        this.loading = false
      }
    },

    async createProject() {
      if (!this.newProject.name.trim()) {
        this.$message.warning('请输入项目名称')
        return
      }

      this.creating = true
      try {
        const res = await projectApi.create(this.newProject)
        this.$store.commit('ADD_PROJECT', res.data)
        this.newProject = { name: '', description: '' }
        this.$message.success('项目创建成功')
      } catch (error) {
        // 错误已由拦截器处理
      } finally {
        this.creating = false
      }
    },

    selectProject(project) {
      this.$store.dispatch('selectProject', project)
      this.$router.push('/testcases')
    },

    formatDate(dateStr) {
      if (!dateStr) return ''
      const date = new Date(dateStr)
      const year = date.getFullYear()
      const month = String(date.getMonth() + 1).padStart(2, '0')
      const day = String(date.getDate()).padStart(2, '0')
      return `${year}-${month}-${day}`
    }
  }
}
</script>

<style scoped>
.home-page {
  max-width: 1400px;
  margin: 0 auto;
}

.create-project-card {
  margin-bottom: 20px;
}

.card-title {
  font-size: 18px;
  font-weight: 600;
  color: #333;
}

.project-card {
  background: white;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 20px;
  cursor: pointer;
  transition: all 0.3s;
  border: 2px solid transparent;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}

.project-card:hover {
  border-color: #667eea;
  transform: translateY(-2px);
  box-shadow: 0 4px 16px rgba(102, 126, 234, 0.2);
}

.project-name {
  font-size: 16px;
  font-weight: 600;
  color: #333;
  margin-bottom: 8px;
}

.project-desc {
  color: #666;
  font-size: 14px;
  margin-bottom: 12px;
  min-height: 40px;
}

.project-meta {
  display: flex;
  gap: 15px;
  color: #999;
  font-size: 12px;
}

.empty-state {
  text-align: center;
  padding: 60px 20px;
  color: #999;
}

.empty-icon {
  font-size: 64px;
  margin-bottom: 20px;
  opacity: 0.5;
}
</style>
