<template>
  <div className="dashboard-container">
    <AssetOverview
        :user-data="userData"
        :system-time="systemTime"
        :market-status="marketStatus"
        @open-transfer="transferDialogVisible = true"
    />

    <div className="chart-section">
      <PerformanceChart :user-data="userData"/>
    </div>

    <MyStrategies />

    <PositionList ref="positionListRef"/>

    <div className="table-section">
      <RecentOrders
          :orders="recentOrders"
          :loading="tableLoading"
          @refresh="manualRefresh"
      />
    </div>

    <BankTransferDialog
        v-model:visible="transferDialogVisible"
        :user-data="userData"
        @success="manualRefresh"
    />
  </div>
</template>

<script setup>
import {ref, onMounted, onUnmounted} from 'vue'
import axios from 'axios'
import {useRouter} from 'vue-router'

import AssetOverview from '../components/AssetOverview.vue'
import RecentOrders from '../components/RecentOrders.vue'
import BankTransferDialog from '../components/BankTransferDialog.vue'
import PerformanceChart from '../components/PerformanceChart.vue'
import PositionList from '../components/PositionList.vue'
// 🟢 引入策略组件
import MyStrategies from '../components/MyStrategies.vue'

const router = useRouter()
const loading = ref(true)
const tableLoading = ref(false)
const timer = ref(null)
const localTickTimer = ref(null)
const positionListRef = ref(null)

const transferDialogVisible = ref(false)

const systemTime = ref('')
const marketStatus = ref('获取中...')
const currentLocalTime = ref(null)

const userData = ref({
  total_assets: 0,
  market_value: 0,
  balance: 0,
  withdrawable: 0,
  daily_profit: 0,
  total_profit: 0,
  initial_capital: 200000
})

const recentOrders = ref([])

const getApi = () => {
  return axios.create({
    baseURL: 'http://127.0.0.1:8000/',
    headers: {'Authorization': 'Token ' + localStorage.getItem('token')}
  })
}

const manualRefresh = () => {
  tableLoading.value = true
  fetchDashboardData().finally(() => {
    tableLoading.value = false
  })
}

const checkMarketStatus = (timeStr) => {
  if (!timeStr) return '获取中...'
  const cleanTimeStr = timeStr.replace(/-/g, '/')
  const date = new Date(cleanTimeStr)
  if (isNaN(date.getTime())) return '解析错误'

  const day = date.getDay()
  if (day === 0 || day === 6) return '休市 (周末)'

  const hours = date.getHours()
  const minutes = date.getMinutes()
  const timeNum = hours * 100 + minutes

  if (timeNum < 930) return '未开盘'
  if (timeNum >= 930 && timeNum <= 1130) return '交易中'
  if (timeNum > 1130 && timeNum < 1300) return '午间休市'
  if (timeNum >= 1300 && timeNum < 1500) return '交易中'
  return '已收盘'
}

const fetchDashboardData = async () => {
  const api = getApi()
  try {
    const userRes = await api.get('api/users/info/').catch(() => api.get('users/api/info/'))
    if (userRes && userRes.data.code === 200) {
      userData.value = userRes.data.data
      const assets = parseFloat(userData.value.total_assets) || 0
      const initial = parseFloat(userData.value.initial_capital) || 200000
      userData.value.total_profit = assets - initial
    }

    const ordersRes = await api.get('trade/api/orders/').catch(() => api.get('api/trade/orders/').catch(() => null))
    if (ordersRes && ordersRes.data.code === 200) {
      recentOrders.value = ordersRes.data.data || []
    }

    const timeRes = await api.get('trade/api/time/').catch(() => null)
    if (timeRes && timeRes.data.code === 200) {
      const serverTimeStr = timeRes.data.data.system_time
      currentLocalTime.value = new Date(serverTimeStr.replace(/-/g, '/'))
      systemTime.value = serverTimeStr
      marketStatus.value = checkMarketStatus(systemTime.value)
    }

    if (positionListRef.value) {
      positionListRef.value.fetchData()
    }

  } catch (e) {
    if (e.response && e.response.status === 401) {
      if (timer.value) clearInterval(timer.value)
      if (localTickTimer.value) clearInterval(localTickTimer.value)
      router.push('/login')
    }
    console.error('Data sync failed:', e)
  }
}

onMounted(() => {
  fetchDashboardData().finally(() => {
    loading.value = false
  })

  timer.value = setInterval(() => {
    fetchDashboardData()
  }, 3000)

  localTickTimer.value = setInterval(() => {
    if (currentLocalTime.value) {
      currentLocalTime.value.setSeconds(currentLocalTime.value.getSeconds() + 1)

      const y = currentLocalTime.value.getFullYear()
      const m = String(currentLocalTime.value.getMonth() + 1).padStart(2, '0')
      const d = String(currentLocalTime.value.getDate()).padStart(2, '0')
      const h = String(currentLocalTime.value.getHours()).padStart(2, '0')
      const min = String(currentLocalTime.value.getMinutes()).padStart(2, '0')
      const s = String(currentLocalTime.value.getSeconds()).padStart(2, '0')

      systemTime.value = y + '-' + m + '-' + d + ' ' + h + ':' + min + ':' + s
      marketStatus.value = checkMarketStatus(systemTime.value)
    }
  }, 1000)
})

onUnmounted(() => {
  if (timer.value) clearInterval(timer.value)
  if (localTickTimer.value) clearInterval(localTickTimer.value)
})
</script>

<style scoped>
.dashboard-container {
  padding: 20px;
  background-color: #f8f9fa;
  min-height: 100vh;
}
.chart-section { margin-bottom: 20px; }
.table-section { margin-top: 20px; }
</style>