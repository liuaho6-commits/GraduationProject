<template>
  <el-card class="asset-panel-card" shadow="never">
    <div class="asset-main">
      <div class="total-assets-box">
        <span class="label">总资产 (元)</span>
        <h2 class="total-value">¥ {{ formatNumber(userData.total_assets) }}</h2>
      </div>
      <div class="profit-summary">
        <div class="profit-item">
          <span class="label">当日收益</span>
          <span :class="getPriceClass(userData.daily_profit)">
            {{ userData.daily_profit >= 0 ? '+' : '' }}{{ formatNumber(userData.daily_profit) }}
            <span class="rate-text">({{ dailyReturnRate }})</span>
          </span>
        </div>
        <div class="profit-item">
          <span class="label">累计总收益</span>
          <span :class="getPriceClass(userData.total_profit)">
            {{ userData.total_profit >= 0 ? '+' : '' }}{{ formatNumber(userData.total_profit) }}
            <span class="rate-text">({{ totalReturnRate }})</span>
          </span>
        </div>
      </div>
    </div>
    <el-divider />
    <el-row :gutter="20" class="asset-grid">
      <el-col :span="6">
        <div class="grid-item">
          <span class="label">总市值</span>
          <span class="value">¥ {{ formatNumber(userData.market_value) }}</span>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="grid-item">
          <span class="label">可用余额</span>
          <span class="value">¥ {{ formatNumber(userData.balance) }}</span>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="grid-item">
          <span class="label">可取资金</span>
          <span class="value">¥ {{ formatNumber(userData.withdrawable) }}</span>
        </div>
      </el-col>
      <el-col :span="6" class="action-col">
        <el-button type="primary" size="small" @click="$emit('open-transfer')">银证转账</el-button>
      </el-col>
    </el-row>
  </el-card>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  userData: {
    type: Object,
    required: true,
    default: () => ({
      total_assets: 0,
      market_value: 0,
      balance: 0,
      withdrawable: 0,
      daily_profit: 0,
      total_profit: 0,
      initial_capital: 200000
    })
  }
})

defineEmits(['open-transfer'])

const formatNumber = (num) => {
  return Number(num || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

const getPriceClass = (val) => {
  if (val > 0) return 'up'
  if (val < 0) return 'down'
  return ''
}

const totalReturnRate = computed(() => {
  const initial = props.userData.initial_capital || 1
  const profit = props.userData.total_profit || 0
  const rate = (profit / initial) * 100
  return (rate > 0 ? '+' : '') + rate.toFixed(2) + '%'
})

const dailyReturnRate = computed(() => {
  const currentAssets = props.userData.total_assets || 0
  const dailyProfit = props.userData.daily_profit || 0
  const yesterdayAssets = currentAssets - dailyProfit

  if (yesterdayAssets <= 0) return '0.00%'
  const rate = (dailyProfit / yesterdayAssets) * 100
  return (rate > 0 ? '+' : '') + rate.toFixed(2) + '%'
})
</script>

<style scoped>
.asset-panel-card { border-radius: 12px; margin-bottom: 20px; border: none; box-shadow: 0 4px 12px rgba(0,0,0,0.05) !important; }
.asset-main { display: flex; justify-content: space-between; align-items: center; padding: 10px 20px; }
.total-assets-box { display: flex; flex-direction: column; }
.total-value { font-size: 36px; font-weight: 700; margin: 8px 0; color: #1a1a1a; font-family: 'DIN Alternate', sans-serif; }
.profit-summary { display: flex; gap: 40px; }
.profit-item { display: flex; flex-direction: column; align-items: flex-end; }
.profit-item span:nth-child(2) { font-size: 20px; font-weight: 600; margin-top: 4px; display: flex; align-items: baseline; gap: 5px; }
.rate-text { font-size: 13px; font-weight: 400; opacity: 0.8; }
.asset-grid { padding: 10px 20px; }
.grid-item { display: flex; flex-direction: column; gap: 8px; }
.grid-item .value { font-size: 18px; font-weight: 600; color: #2c3e50; }
.action-col { display: flex; align-items: center; justify-content: flex-end; }
.label { font-size: 13px; color: #909399; }
.up { color: #f56c6c; }
.down { color: #67c23a; }
</style>