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
             <el-radio-button label="daily">日K</el-radio-button>
             <el-radio-button label="min">分时</el-radio-button>
           </el-radio-group>
         </div>
      </template>
    </el-page-header>

    <div class="main-content">
      <div class="chart-wrapper" v-loading="loading">
        <StockDailyChart
          v-if="viewMode === 'daily'"
          :data="chartData"
        />
        <StockMinuteChart
          v-if="viewMode === 'min'"
          :data="chartData"
          :pre-close="preClose"
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
                  :step="0.01"
                  style="width: 100%"
                  :disabled="true"
                  :controls="false"
               />
               <div class="price-hint">当前无挂单机制，以市价(买一/卖一)成交</div>
            </el-form-item>

            <el-form-item label="委托数量">
               <el-input-number v-model="tradeVolume" :step="100" style="width: 100%" />
               <div class="quick-btns">
                 <el-button size="small" @click="setVolume(0.33)">1/3</el-button>
                 <el-button size="small" @click="setVolume(0.5)">1/2</el-button>
                 <el-button size="small" @click="setVolume(1.0)">全仓</el-button>
               </div>
            </el-form-item>

            <div class="asset-info">
               <div v-if="tradeDirection === 'buy'">
                 <small>可用资金: ¥{{ userBalance.toLocaleString() }}</small>
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
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { Clock } from '@element-plus/icons-vue'

import StockDailyChart from '../components/StockDailyChart.vue'
import StockMinuteChart from '../components/StockMinuteChart.vue'

const route = useRoute()
const router = useRouter()
const stockCode = route.params.code

const stockName = ref('')
const systemTimeDisplay = ref('')
const chartData = ref([])
const preClose = ref(0)
const loading = ref(false)
const viewMode = ref('daily')

// 交易相关
const tradeDirection = ref('buy')
const tradePrice = ref(0)
const latestPrice = ref(0)
const tradeVolume = ref(100)
const userBalance = ref(0)
const userPosition = ref(0)

let refreshTimer = null
const api = axios.create({
  baseURL: 'http://127.0.0.1:8000/',
  headers: { 'Authorization': `Token ${localStorage.getItem('token')}` }
})

// 自动更新交易价格
const updateTradePrice = () => {
    if (latestPrice.value > 0) {
        tradePrice.value = latestPrice.value
    }
}

// 快捷仓位计算
const setVolume = (ratio) => {
    if (tradePrice.value <= 0) return ElMessage.warning('当前价格无效')

    if (tradeDirection.value === 'buy') {
        const money = userBalance.value * ratio
        const vol = Math.floor(money / tradePrice.value / 100) * 100
        tradeVolume.value = vol
    } else {
        const vol = Math.floor(userPosition.value * ratio / 100) * 100
        tradeVolume.value = (ratio === 1.0) ? userPosition.value : vol
    }
}

const fetchStockData = async (freq, date = null, silent = false) => {
  if (!silent) loading.value = true
  try {
    let url = `stocks/api/data/${stockCode}/?freq=${freq}`
    if (date) url += `&date=${date}`
    const res = await api.get(url)

    if (res.data.code === 200) {
      stockName.value = res.data.name
      systemTimeDisplay.value = res.data.current_mock_time || ''

      const raw = res.data.data
      chartData.value = raw

      if (raw.length > 0) {
          latestPrice.value = raw[raw.length - 1].close
          updateTradePrice()
      }

      if (res.data.pre_close) preClose.value = parseFloat(res.data.pre_close)
    }
  } catch (err) {
      if (!silent) console.error(err)
  } finally {
      if (!silent) loading.value = false
  }
}

const fetchUserAssets = async () => {
    try {
        const userRes = await api.get('api/users/info/')
        if (userRes.data.code === 200) {
            userBalance.value = parseFloat(userRes.data.data.balance || 0)
        }
        const posRes = await api.get(`api/trade/position/${stockCode}/`)
        if (posRes.data.code === 200) {
            userPosition.value = posRes.data.data.volume || 0
        }
    } catch (e) { console.error(e) }
}

const handleTrade = async () => {
    if (tradeVolume.value <= 0) return ElMessage.warning('数量必须大于0')
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
            ElMessage.error(res.data.msg)
        }
    } catch (e) {
        ElMessage.error('交易请求失败')
    }
}

const handleViewChange = (val) => {
    chartData.value = []
    fetchStockData(val, null, false)
}

const goBack = () => router.push('/market')

watch(tradeDirection, updateTradePrice)

onMounted(() => {
    fetchStockData(viewMode.value, null, false)
    fetchUserAssets()
    refreshTimer = setInterval(() => {
        if (viewMode.value === 'min') fetchStockData('min', null, true)
    }, 1000)
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

/* 🟢 修改点：调整了高度，从 600px 减小到 450px */
.chart-wrapper {
  flex: 1;
  background: #fff;
  border-radius: 8px;
  padding: 10px;
  height: 450px; /* 之前是 600px */
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
.live-tag { display: flex; align-items: center; gap: 4px; }
.dot { width: 6px; height: 6px; background: #67c23a; border-radius: 50%; display: inline-block; animation: pulse 1.5s infinite; }
.price-hint { font-size: 12px; color: #999; margin-top: 4px; }

@keyframes pulse {
  0% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(1.2); }
  100% { opacity: 1; transform: scale(1); }
}
</style>