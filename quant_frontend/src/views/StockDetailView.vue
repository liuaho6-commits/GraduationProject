<template>
  <div class="detail-container">
    <StockHeader
      :stock-name="stockName"
      :stock-code="stockCode"
      :system-time="systemTimeDisplay"
      v-model:view-mode="viewMode"
      @back="goBack"
      @update:view-mode="handleViewChange"
    />

    <div class="main-content">
      <div class="chart-wrapper" v-loading="chartLoading">
        <StockChart
          :data="chartData"
          :freq="viewMode"
        />
      </div>

      <TradePanel
        :stock-code="stockCode"
        :latest-price="latestPrice"
        :user-balance="userBalance"
        :user-position="userPosition"
        @trade-success="fetchUserAssets"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import StockChart from '../components/StockChart.vue'
import StockHeader from '../components/StockHeader.vue'
import TradePanel from '../components/TradePanel.vue'

const route = useRoute()
const router = useRouter()
const stockCode = route.params.code

// 状态定义
const stockName = ref('加载中...')
const systemTimeDisplay = ref('')
const chartData = ref([])
const chartLoading = ref(false)
const viewMode = ref('min')

const latestPrice = ref(0)
const userBalance = ref(0)
const userPosition = ref(0)

let refreshTimer = null

const getApi = () => {
  return axios.create({
    baseURL: 'http://127.0.0.1:8000/',
    headers: { 'Authorization': `Token ${localStorage.getItem('token')}` }
  })
}

// 获取行情数据（价格、名称、时间）
const fetchQuote = async () => {
  const api = getApi()
  try {
    const res = await api.get(`stocks/api/data/${stockCode}/?freq=min`)
    if (res.data.code === 200) {
      const data = res.data.data
      if (data && data.length > 0) {
        latestPrice.value = parseFloat(data[data.length - 1].close)
      }
      stockName.value = res.data.name
      systemTimeDisplay.value = res.data.current_mock_time || ''
    }
  } catch (e) {
    console.error("Quote error", e)
  }
}

// 获取图表数据
const fetchChartData = async (silent = false) => {
  if (!viewMode.value) return
  if (!silent) chartLoading.value = true

  const api = getApi()
  try {
    const res = await api.get(`stocks/api/data/${stockCode}/?freq=${viewMode.value}`)
    if (res.data.code === 200) {
      chartData.value = res.data.data
    }
  } catch (err) {
    console.error("Chart error", err)
  } finally {
    if (!silent) chartLoading.value = false
  }
}

// 获取用户资产和持仓
const fetchUserAssets = async () => {
  const api = getApi()
  try {
    // 获取余额
    const userRes = await api.get('api/users/info/').catch(() => api.get('users/api/info/'))
    if (userRes && userRes.data.code === 200) {
      const data = userRes.data.data || userRes.data
      userBalance.value = parseFloat(data.balance || 0)
    }
    // 获取特定股票持仓
    const posRes = await api.get(`api/trade/position/${stockCode}/`)
    if (posRes && posRes.data.code === 200) {
      userPosition.value = posRes.data.data.volume || 0
    }
  } catch (e) {
    console.error(e)
  }
}

const handleViewChange = () => {
  chartData.value = []
  fetchChartData()
}

const goBack = () => router.push('/market')

onMounted(() => {
  fetchQuote()
  fetchChartData()
  fetchUserAssets()

  // 轮询更新行情和分时图
  refreshTimer = setInterval(() => {
    fetchQuote()
    // 只有在分时模式下才轮询图表数据
    if (viewMode.value === 'min') {
      fetchChartData(true) // silent refresh
    }
  }, 2000)
})

onBeforeUnmount(() => {
  if (refreshTimer) clearInterval(refreshTimer)
})
</script>

<style scoped>
.detail-container { padding: 20px; background-color: #f8fafc; min-height: 100vh; }
.main-content { display: flex; gap: 20px; align-items: flex-start; }

.chart-wrapper {
  flex: 1;
  background: #fff;
  border-radius: 8px;
  padding: 10px;
  height: 450px;
  min-height: 450px;
  box-shadow: 0 2px 12px 0 rgba(0,0,0,0.05);
}
</style>