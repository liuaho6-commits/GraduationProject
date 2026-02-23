<template>
  <div className="dashboard-container">
    <AssetOverview
        :user-data="userData"
        @open-transfer="transferDialogVisible = true"
    />

    <div className="chart-section">
      <PerformanceChart :user-data="userData"/>
    </div>

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

// 引入拆分后的组件
import AssetOverview from '../components/AssetOverview.vue'
import RecentOrders from '../components/RecentOrders.vue'
import BankTransferDialog from '../components/BankTransferDialog.vue'

// 保持原有的组件
import PerformanceChart from '../components/PerformanceChart.vue'
import PositionList from '../components/PositionList.vue'

const router = useRouter()
const loading = ref(true) // 全局loading，这里暂时只用于初始化
const tableLoading = ref(false)
const timer = ref(null)
const positionListRef = ref(null)

const transferDialogVisible = ref(false)

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
    headers: {'Authorization': `Token ${localStorage.getItem('token')}`}
  })
}

const manualRefresh = () => {
  tableLoading.value = true
  fetchDashboardData().finally(() => {
    tableLoading.value = false
  })
}

const fetchDashboardData = async () => {
  const api = getApi()
  try {
    // 1. 获取基础资产信息
    const userRes = await api.get('api/users/info/').catch(() => api.get('users/api/info/'))
    if (userRes && userRes.data.code === 200) {
      userData.value = userRes.data.data
      // 修正总收益计算 (如果你后端没算，就在前端算)
      const assets = parseFloat(userData.value.total_assets) || 0
      const initial = parseFloat(userData.value.initial_capital) || 200000
      userData.value.total_profit = assets - initial
    }

    // 2. 获取订单记录
    const ordersRes = await api.get('api/trade/orders/').catch(() => null)
    if (ordersRes && ordersRes.data.code === 200) {
      recentOrders.value = ordersRes.data.data || []
    }

    // 3. 刷新持仓组件的数据
    if (positionListRef.value) {
      positionListRef.value.fetchData()
    }

  } catch (e) {
    if (e.response && e.response.status === 401) {
      if (timer.value) clearInterval(timer.value)
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
})

onUnmounted(() => {
  if (timer.value) {
    clearInterval(timer.value)
  }
})
</script>

<style scoped>
.dashboard-container {
  padding: 20px;
  background-color: #f8f9fa;
  min-height: 100vh;
}

.chart-section {
  margin-bottom: 20px;
}

.table-section {
  margin-top: 20px;
}
</style>