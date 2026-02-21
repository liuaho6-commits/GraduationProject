<template>
  <div class="detail-container">
    <el-page-header @back="goBack" class="custom-header">
      <template #content>
        <div class="header-left">
          <span class="stock-title">{{ stockName }} <span class="stock-code">({{ stockCode }})</span></span>
          <transition name="el-fade-in">
            <el-tag v-if="viewMode === 'min'" type="success" effect="light" round size="small" class="live-tag">
              <span class="dot"></span> 盘中直播
            </el-tag>
          </transition>
        </div>
      </template>

      <template #extra>
         <div class="header-right">
           <div class="time-display" v-if="systemTimeDisplay">
             <el-icon><Clock /></el-icon> {{ systemTimeDisplay }}
           </div>

           <el-radio-group v-model="viewMode" size="small" @change="handleViewChange">
             <el-radio-button value="min">分时</el-radio-button>
             <el-radio-button value="daily">日K</el-radio-button>
           </el-radio-group>
         </div>
      </template>
    </el-page-header>

    <div class="main-content">
      <div class="chart-wrapper" v-loading="loading">
        <StockChart
          :data="chartData"
          :freq="viewMode"
        />
      </div>

      <div class="trade-panel">
        <el-card shadow="hover">
          <template #header>
             <div class="panel-header">交易下单</div>
          </template>

          <el-tabs v-model="tradeDirection" type="card" class="trade-tabs">
            <el-tab-pane label="买入" name="buy"></el-tab-pane>
            <el-tab-pane label="卖出" name="sell"></el-tab-pane>
          </el-tabs>

          <el-form label-position="top">
            <el-form-item label="委托价格 (市价)">
               <el-input-number
                  v-model="tradePrice"
                  :precision="2"
                  :step="0.01"
                  style="width: 100%"
                  :disabled="true"
                  :controls="false"
               />
               <div class="price-hint">当前市价: ¥{{ formatPrice(latestPrice) }} (实时变动)</div>
            </el-form-item>

            <el-form-item label="委托数量">
               <el-input-number v-model="tradeVolume" :step="100" :min="0" step-strictly style="width: 100%" />
               <div class="quick-btns">
                 <el-button size="small" @click="setVolume(0.33)">1/3</el-button>
                 <el-button size="small" @click="setVolume(0.5)">1/2</el-button>
                 <el-button size="small" @click="setVolume(1.0)">全仓</el-button>
               </div>
            </el-form-item>

            <div class="asset-info">
               <div v-if="tradeDirection === 'buy'">
                 <small :class="{ 'text-danger': latestPrice > 0 && userBalance < latestPrice * 100 }">
                   可用资金: ¥{{ formatPrice(userBalance) }}
                   <span v-if="latestPrice > 0 && userBalance < latestPrice * 100"> (余额不足)</span>
                 </small>
               </div>
               <div v-else>
                 <small>持仓股数: {{ userPosition }}</small>
               </div>
            </div>

            <el-button
              type="primary"
              class="trade-btn"
              :class="tradeDirection === 'buy' ? 'buy-btn' : 'sell-btn'"
              @click="handleTrade"
              :loading="tradeLoading"
              :disabled="tradeDirection === 'buy' && latestPrice > 0 && userBalance < latestPrice * 100"
            >
              {{ tradeDirection === 'buy' ? '买入' : '卖出' }}
            </el-button>
          </el-form>
        </el-card>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { Clock } from '@element-plus/icons-vue'
import StockChart from '../components/StockChart.vue'

const route = useRoute()
const router = useRouter()
const stockCode = route.params.code

const stockName = ref('加载中...')
const systemTimeDisplay = ref('')
const chartData = ref([])
const loading = ref(false)
const viewMode = ref('min')

const tradeDirection = ref('buy')
const tradePrice = ref(0)
const latestPrice = ref(0)
// 🟢 核心修改1：默认值直接给 0，防止刷新瞬间显示 100
const tradeVolume = ref(0)
const userBalance = ref(0)
const userPosition = ref(0)
const tradeLoading = ref(false)

let refreshTimer = null

const getApi = () => {
  return axios.create({
    baseURL: 'http://127.0.0.1:8000/',
    headers: { 'Authorization': `Token ${localStorage.getItem('token')}` }
  })
}

const formatPrice = (val) => {
    return Number(val).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})
}

// 🟢 辅助函数：检查是否能买得起一手，智能设置默认值
// 只有当 tradeVolume 还是 0 (初始状态) 且 钱够买一手时，才自动填 100
const trySetDefaultVolume = () => {
    if (tradeDirection.value === 'buy' && tradeVolume.value === 0 && latestPrice.value > 0) {
        if (userBalance.value >= latestPrice.value * 100) {
            tradeVolume.value = 100
        }
        // 如果买不起，保持 0，什么都不做
    }
}

const fetchQuote = async () => {
    const api = getApi()
    try {
        const res = await api.get(`stocks/api/data/${stockCode}/?freq=min`)
        if (res.data.code === 200) {
             const data = res.data.data
             if (data && data.length > 0) {
                 const newPrice = parseFloat(data[data.length - 1].close)
                 latestPrice.value = newPrice
                 tradePrice.value = parseFloat(newPrice.toFixed(2))
                 trySetDefaultVolume() // 价格更新了，试着重置默认值
             }
             stockName.value = res.data.name
             systemTimeDisplay.value = res.data.current_mock_time || ''
        }
    } catch (e) { console.error("Quote error", e) }
}

const fetchChartData = async () => {
    if(!viewMode.value) return
    loading.value = true
    const api = getApi()
    try {
        const res = await api.get(`stocks/api/data/${stockCode}/?freq=${viewMode.value}`)
        if (res.data.code === 200) {
            chartData.value = res.data.data
        }
    } catch (err) {
        console.error("Chart error", err)
    } finally {
        loading.value = false
    }
}

const fetchUserAssets = async () => {
    const api = getApi()
    try {
        const userRes = await api.get('api/users/info/').catch(()=>null) || await api.get('users/api/info/')
        if (userRes && userRes.data.code === 200) {
            const data = userRes.data.data || userRes.data
            userBalance.value = parseFloat(data.balance || 0)
            trySetDefaultVolume() // 余额更新了，试着重置默认值
        }
        const posRes = await api.get(`api/trade/position/${stockCode}/`)
        if (posRes && posRes.data.code === 200) {
            userPosition.value = posRes.data.data.volume || 0
        }
    } catch (e) { console.error(e) }
}

const setVolume = (ratio) => {
    if (tradePrice.value <= 0) return

    if (tradeDirection.value === 'buy') {
        const money = userBalance.value * ratio
        // 计算最大可买手数
        const maxHand = Math.floor(money / tradePrice.value / 100)

        // 🟢 核心修改2：如果买不起，直接静默置 0，移除所有 ElMessage.warning
        if (maxHand < 1) {
            tradeVolume.value = 0
        } else {
            tradeVolume.value = maxHand * 100
        }
    } else {
        const vol = Math.floor(userPosition.value * ratio / 100) * 100
        tradeVolume.value = (ratio === 1.0) ? userPosition.value : vol
    }
}

const handleTrade = async () => {
    if (tradeVolume.value <= 0) return ElMessage.warning('数量必须大于0')
    tradeLoading.value = true
    const api = getApi()
    try {
        const res = await api.post('api/trade/place_order/', {
            stock_code: stockCode,
            direction: tradeDirection.value,
            price: tradePrice.value,
            volume: tradeVolume.value
        })
        if (res.data.code === 200) {
            ElMessage.success('委托提交成功')
            fetchUserAssets()
        } else {
            ElMessage.error(res.data.msg || '交易失败')
        }
    } catch (e) {
        ElMessage.error('交易请求失败')
    } finally {
        tradeLoading.value = false
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
    refreshTimer = setInterval(() => {
        const api = getApi()
        fetchQuote()
        if (viewMode.value === 'min') {
             api.get(`stocks/api/data/${stockCode}/?freq=min`).then(res => {
                 if(res.data.code === 200) chartData.value = res.data.data
             })
        }
    }, 2000)
})

onBeforeUnmount(() => {
    if (refreshTimer) clearInterval(refreshTimer)
})
</script>

<style scoped>
.detail-container { padding: 20px; background-color: #f8fafc; min-height: 100vh; }
.custom-header { background: #fff; padding: 12px 20px; border-radius: 8px; margin-bottom: 20px; }
.header-left { display: flex; align-items: center; gap: 12px; }
.stock-title { font-size: 22px; font-weight: 700; color: #1e293b; }
.stock-code { font-size: 14px; color: #64748b; font-weight: normal; margin-left: 6px; }
.time-display { font-family: 'Roboto Mono', monospace; font-size: 14px; color: #64748b; margin-right: 15px; }

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

.trade-panel { width: 340px; flex-shrink: 0; }

.quick-btns { display: flex; gap: 5px; margin-top: 8px; }
.quick-btns .el-button { flex: 1; }
.trade-btn { width: 100%; margin-top: 15px; font-weight: bold; }
.buy-btn { background-color: #f56c6c; border-color: #f56c6c; }
.sell-btn { background-color: #67c23a; border-color: #67c23a; }
.asset-info { margin-top: 10px; color: #666; font-size: 13px; background: #f1f5f9; padding: 8px; border-radius: 4px; }
.text-danger { color: #f56c6c; font-weight: bold; }
.live-tag { display: flex; align-items: center; gap: 4px; }
.dot { width: 6px; height: 6px; background: #67c23a; border-radius: 50%; display: inline-block; animation: pulse 1.5s infinite; }
.price-hint { font-size: 12px; color: #999; margin-top: 4px; }

@keyframes pulse {
  0% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(1.2); }
  100% { opacity: 1; transform: scale(1); }
}
</style>