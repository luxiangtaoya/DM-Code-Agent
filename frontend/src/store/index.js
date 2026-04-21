import Vue from 'vue'
import Vuex from 'vuex'

Vue.use(Vuex)

export default new Vuex.Store({
  state: {
    // 当前选中的项目
    currentProject: null,

    // 项目列表
    projects: [],

    // 测试用例列表
    testCases: [],

    // 执行记录列表
    executions: [],

    // API配置
    apiConfig: {
      baseURL: process.env.VUE_APP_API_BASE_URL || 'http://localhost:8000/api/v1',
      timeout: 30000
    }
  },

  mutations: {
    SET_CURRENT_PROJECT(state, project) {
      state.currentProject = project
    },

    SET_PROJECTS(state, projects) {
      state.projects = projects
    },

    ADD_PROJECT(state, project) {
      state.projects.push(project)
    },

    DELETE_PROJECT(state, projectId) {
      state.projects = state.projects.filter(p => p.id !== projectId)
      // 如果删除的是当前选中的项目，清空选择
      if (state.currentProject && state.currentProject.id === projectId) {
        state.currentProject = null
      }
    },

    SET_TEST_CASES(state, testCases) {
      state.testCases = testCases
    },

    SET_EXECUTIONS(state, executions) {
      state.executions = executions
    }
  },

  actions: {
    async fetchProjects({ commit, state }) {
      const { data } = await state.api.baseURL + '/projects'
      // 实际API调用
      commit('SET_PROJECTS', data.data || [])
    },

    selectProject({ commit }, project) {
      commit('SET_CURRENT_PROJECT', project)
    }
  },

  getters: {
    hasCurrentProject: state => !!state.currentProject,
    currentProjectId: state => state.currentProject?.id
  }
})
