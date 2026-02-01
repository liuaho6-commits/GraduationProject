<template>
  <el-container class="layout-container">
    <el-aside width="220px" class="aside">
      <div class="logo">
        <el-icon><TrendCharts /></el-icon>
        <span>QuantTrader</span>
      </div>
      <el-menu
        :default-active="activeMenu"
        class="el-menu-vertical"
        background-color="#304156"
        text-color="#bfcbd9"
        active-text-color="#409EFF"
        router
      >
        <el-menu-item index="/dashboard">
          <el-icon><Odometer /></el-icon>
          <span>仪表盘</span>
        </el-menu-item>
        <el-menu-item index="/market">
          <el-icon><DataLine /></el-icon>
          <span>行情中心</span>
        </el-menu-item>
        </el-menu>
    </el-aside>

    <el-container>
      <el-header class="header">
        <div class="header-left">
          </div>
        <div class="header-right">
          <el-dropdown @command="handleCommand">
            <span class="el-dropdown-link">
              <el-avatar :size="32" :src="userInfo.avatar || defaultAvatar" />
              <span class="username">{{ userInfo.username || '用户' }}</span>
              <el-icon class="el-icon--right"><arrow-down /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="logout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <el-main class="main-content">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { TrendCharts, Odometer, DataLine, ArrowDown } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

const route = useRoute()
const router = useRouter()
const defaultAvatar = 'https://cube.elemecdn.com/0/88/03b0d39583f48206768a7534e55bcpng.png'

const userInfo = ref({ username: '', avatar: '' })

// 🟢 核心修复：安全的 JSON 解析逻辑
const loadUserInfo = () => {
  try {
    const userStr = localStorage.getItem('user') || localStorage.getItem('token') // 尝试获取用户信息

    // 如果是 undefined 字符串、null 或者空，直接返回默认空对象，不报错
    if (!userStr || userStr === 'undefined' || userStr === 'null') {
        userInfo.value = { username: 'Guest' }
        return
    }

    // 尝试解析
    const parsed = JSON.parse(userStr)
    // 兼容不同的存储结构（有的存的是整个对象，有的可能只是名字）
    if (typeof parsed === 'object') {
        userInfo.value = parsed
    } else {
        userInfo.value = { username: 'User' }
    }
  } catch (e) {
    console.warn('LocalStorage user info parse failed, resetting...', e)
    // 解析失败时，为了防止下次还崩，建议清空错误的缓存
    localStorage.removeItem('user')
    userInfo.value = { username: 'Guest' }
  }
}

const activeMenu = computed(() => {
  return route.path
})

const handleCommand = (command) => {
  if (command === 'logout') {
    localStorage.clear() // 清空所有缓存
    ElMessage.success('已退出登录')
    router.push('/login')
  }
}

onMounted(() => {
  loadUserInfo()
})
</script>

<style scoped>
.layout-container { height: 100vh; }
.aside { background-color: #304156; display: flex; flex-direction: column; }
.logo { height: 60px; display: flex; align-items: center; justify-content: center; color: #fff; font-size: 20px; font-weight: bold; background-color: #2b3649; gap: 10px; }
.el-menu-vertical { border-right: none; }
.header { background-color: #fff; border-bottom: 1px solid #e6e6e6; display: flex; align-items: center; justify-content: space-between; box-shadow: 0 1px 4px rgba(0,21,41,.08); }
.header-right { margin-right: 20px; cursor: pointer; }
.el-dropdown-link { display: flex; align-items: center; gap: 8px; outline: none; }
.username { font-size: 14px; color: #606266; }
.main-content { background-color: #f0f2f5; padding: 20px; }

/* 页面切换动画 */
.fade-enter-active, .fade-leave-active { transition: opacity 0.3s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>