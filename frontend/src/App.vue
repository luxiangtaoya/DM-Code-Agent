<template>
  <div id="app">
    <!-- 左侧边栏 -->
    <div class="sidebar">
      <div class="sidebar-header" @click="$router.push('/')">
        <span class="logo-icon">🤖</span>
        <span class="logo-text">AI测试平台</span>
      </div>
      <div class="nav-menu">
        <router-link to="/" class="nav-item">
          <i class="el-icon-folder-opened"></i>
          <span>项目管理</span>
        </router-link>
        <router-link to="/testcases" class="nav-item">
          <i class="el-icon-document"></i>
          <span>测试用例</span>
        </router-link>
        <router-link to="/executions" class="nav-item">
          <i class="el-icon-video-play"></i>
          <span>执行记录</span>
        </router-link>
        <router-link to="/reports" class="nav-item">
          <i class="el-icon-data-analysis"></i>
          <span>测试报告</span>
        </router-link>
      </div>
    </div>

    <!-- 主内容区域 -->
    <div class="main-wrapper">
      <div class="main-content">
        <router-view />
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'App'
}
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  background: #f5f7fa;
}

#app {
  display: flex;
  min-height: 100vh;
}

.sidebar {
  width: 220px;
  background: linear-gradient(180deg, #2c3e50 0%, #34495e 100%);
  color: white;
  display: flex;
  flex-direction: column;
  position: fixed;
  height: 100vh;
  left: 0;
  top: 0;
  box-shadow: 2px 0 12px rgba(0,0,0,0.1);
  z-index: 100;
}

.sidebar-header {
  padding: 20px;
  display: flex;
  align-items: center;
  gap: 12px;
  cursor: pointer;
  border-bottom: 1px solid rgba(255,255,255,0.1);
}

.logo-icon {
  font-size: 32px;
}

.logo-text {
  font-size: 18px;
  font-weight: bold;
}

.nav-menu {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 16px 8px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  color: rgba(255,255,255,0.8);
  text-decoration: none;
  border-radius: 8px;
  transition: all 0.3s;
}

.nav-item i {
  font-size: 18px;
}

.nav-item span {
  font-size: 14px;
}

.nav-item:hover {
  background: rgba(255,255,255,0.1);
  color: white;
}

.nav-item.router-link-active {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  font-weight: 500;
}

.main-wrapper {
  flex: 1;
  margin-left: 220px;
  min-height: 100vh;
}

.main-content {
  padding: 24px;
  max-width: 1600px;
}
</style>
