<template>
  <div class="testcase-detail-page">
    <el-card>
      <div slot="header">
        <el-page-header @back="goBack" content="测试用例详情" />
      </div>
      <div class="empty-state">
        <div class="empty-icon">📝</div>
        <p>测试用例详情页面开发中...</p>
      </div>
    </el-card>
  </div>
</template>

<script>
export default {
  name: 'TestCaseDetail',
  methods: {
    goBack() {
      this.$router.back()
    }
  }
}
</script>

<style scoped>
.testcase-detail-page {
  max-width: 1400px;
  margin: 0 auto;
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
