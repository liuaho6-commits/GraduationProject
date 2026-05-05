<template>
  <div class="index-detail-container">
    <el-page-header @back="goBack" class="page-header">
      <template #content>
        <div class="header-title">
          <span class="name">{{ indexName }}</span>
          <span class="code">({{ indexCode }})</span>
          <el-tag size="small" effect="light" type="info">{{ latestTime || '--' }}</el-tag>
        </div>
      </template>

      <template #extra>
        <el-radio-group v-model="viewMode" size="small" @change="handleViewChange">
          <el-radio-button value="min">5分钟</el-radio-button>
          <el-radio-button value="daily">日K</el-radio-button>
        </el-radio-group>
      </template>
    </el-page-header>

    <el-card shadow="never" class="quote-card">
      <div class="quote-main">
        <div>
          <div class="label">最新点位</div>
          <div class="latest-price">{{ formatPrice(latestPrice) }}</div>
        </div>
        <div>
          <div class="label">数据周期</div>
          <div class="value">{{ viewMode === 'min' ? '5分钟' : '日线' }}</div>
        </div>
        <div>
          <div class="label">K线数量</div>
          <div class="value">{{ chartData.length }}</div>
        </div>
      </div>
    </el-card>

    <div class="chart-panel" v-loading="chartLoading">
      <StockChart :data="chartData" :freq="viewMode" />
    </div>
  </div>
</template>

<script setup>
import { onMounted, onBeforeUnmount, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import StockChart from '../components/StockChart.vue'

const route = useRoute()
const router = useRouter()
const indexCode = route.params.code
const indexName = ref('加载中...')
const latestPrice = ref(0)
const latestTime = ref('')
const chartData = ref([])
const chartLoading = ref(false)
const viewMode = ref('min')
let refreshTimer = null

const api = axios.create({
  baseURL: 'http://127.0.0.1:8000/',
  headers: { Authorization: `Token ${localStorage.getItem('token')}` }
})

const fetchIndexData = async (silent = false) => {
  if (!silent) chartLoading.value = true
  try {
    const limit = viewMode.value === 'daily' ? 1200 : 1200
    const res = await api.get(`stocks/api/index/${indexCode}/?freq=${viewMode.value}&limit=${limit}`)
    if (res.data.code === 200) {
      indexName.value = res.data.name
      chartData.value = res.data.data || []
      latestPrice.value = Number(res.data.latest_price || 0)
      latestTime.value = res.data.latest_time || ''
    }
  } catch (err) {
    console.error(err)
    ElMessage.error('指数行情获取失败')
  } finally {
    if (!silent) chartLoading.value = false
  }
}

const handleViewChange = () => {
  chartData.value = []
  fetchIndexData()
}

const formatPrice = (value) => Number(value || 0).toFixed(2)

const goBack = () => {
  router.push('/market')
}

onMounted(() => {
  fetchIndexData()
  refreshTimer = setInterval(() => {
    if (viewMode.value === 'min') {
      fetchIndexData(true)
    }
  }, 10000)
})

onBeforeUnmount(() => {
  if (refreshTimer) clearInterval(refreshTimer)
})
</script>

<style scoped>
.index-detail-container {
  background-color: #f8fafc;
  min-height: 100vh;
  padding: 20px;
}

.page-header {
  background: #fff;
  border-radius: 8px;
  margin-bottom: 16px;
  padding: 12px 20px;
}

.header-title {
  align-items: center;
  display: flex;
  gap: 10px;
}

.name {
  color: #1e293b;
  font-size: 22px;
  font-weight: 700;
}

.code {
  color: #64748b;
  font-size: 14px;
}

.quote-card {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  margin-bottom: 16px;
}

.quote-main {
  display: grid;
  gap: 20px;
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.label {
  color: #64748b;
  font-size: 12px;
  margin-bottom: 8px;
}

.latest-price {
  color: #0f172a;
  font-family: "Roboto Mono", monospace;
  font-size: 28px;
  font-weight: 800;
}

.value {
  color: #1e293b;
  font-size: 18px;
  font-weight: 700;
}

.chart-panel {
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(15, 23, 42, 0.05);
  height: 540px;
  padding: 10px;
}

@media (max-width: 768px) {
  .quote-main {
    grid-template-columns: 1fr;
  }
}
</style>
