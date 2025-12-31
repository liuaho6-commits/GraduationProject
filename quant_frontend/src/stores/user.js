import { defineStore } from 'pinia'
import axios from 'axios'

export const useUserStore = defineStore('user', {
  state: () => ({
    // 优先从本地存储读取 Token，保证刷新页面不退出
    token: localStorage.getItem('token') || '',
    userInfo: {
      username: '未登录',
      balance: 0,
      total_assets: 0,
      initial_capital: 0
    }
  }),

  actions: {
    // 登录成功后调用这个方法
    setToken(token) {
      this.token = token
      localStorage.setItem('token', token)
    },

    // 退出登录
    logout() {
      this.token = ''
      this.userInfo = {}
      localStorage.removeItem('token')
    },

    // 获取最新用户信息（余额、资产等）
    async fetchUserInfo() {
      if (!this.token) return

      try {
        // 使用 axios 请求后端接口
        // 这里的路径对应我们刚才修好的后端接口
        const res = await axios.get('/api/users/info/', {
          headers: {
            'Authorization': `Token ${this.token}`
          }
        })

        if (res.data.code === 200) {
          this.userInfo = res.data.data
        }
      } catch (error) {
        console.error('获取用户信息失败:', error)
      }
    }
  }
})