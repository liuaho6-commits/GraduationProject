<template>
  <div class="trade-panel-container">
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
          :loading="loading"
          :disabled="tradeDirection === 'buy' && latestPrice > 0 && userBalance < latestPrice * 100"
        >
          {{ tradeDirection === 'buy' ? '买入' : '卖出' }}
        </el-button>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'

const props = defineProps({
  stockCode: { type: String, required: true },
  latestPrice: { type: Number, default: 0 },
  userBalance: { type: Number, default: 0 },
  userPosition: { type: Number, default: 0 }
})

const emit = defineEmits(['trade-success'])

const tradeDirection = ref('buy')
const tradePrice = ref(0)
const tradeVolume = ref(0)
const loading = ref(false)

// 监听最新价，自动更新委托价
watch(() => props.latestPrice, (newVal) => {
  if (newVal > 0) {
    tradePrice.value = parseFloat(newVal.toFixed(2))
    trySetDefaultVolume()
  }
})

// 监听余额，尝试设置默认手数
watch(() => props.userBalance, () => {
  trySetDefaultVolume()
})

const formatPrice = (val) => {
  return Number(val || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

// 智能设置默认值：如果未设置数量且买得起，默认填100
const trySetDefaultVolume = () => {
  if (tradeDirection.value === 'buy' && tradeVolume.value === 0 && props.latestPrice > 0) {
    if (props.userBalance >= props.latestPrice * 100) {
      tradeVolume.value = 100
    }
  }
}

const setVolume = (ratio) => {
  if (tradePrice.value <= 0) return

  if (tradeDirection.value === 'buy') {
    const money = props.userBalance * ratio
    const maxHand = Math.floor(money / tradePrice.value / 100)
    if (maxHand < 1) {
      tradeVolume.value = 0
    } else {
      tradeVolume.value = maxHand * 100
    }
  } else {
    const vol = Math.floor(props.userPosition * ratio / 100) * 100
    // 全仓卖出时如果不是100倍数（比如送股产生的碎股），可能需要特殊处理，这里按100取整
    // 如果想要卖出全部碎股，逻辑需要后端支持，这里保持原逻辑
    tradeVolume.value = (ratio === 1.0) ? props.userPosition : vol
  }
}

const handleTrade = async () => {
  if (tradeVolume.value <= 0) return ElMessage.warning('数量必须大于0')

  loading.value = true
  try {
    const api = axios.create({
      baseURL: 'http://127.0.0.1:8000/',
      headers: { 'Authorization': `Token ${localStorage.getItem('token')}` }
    })

    const res = await api.post('api/trade/place_order/', {
      stock_code: props.stockCode,
      direction: tradeDirection.value,
      price: tradePrice.value,
      volume: tradeVolume.value
    })

    if (res.data.code === 200) {
      ElMessage.success('委托提交成功')
      emit('trade-success') // 通知父组件刷新资产
    } else {
      ElMessage.error(res.data.msg || '交易失败')
    }
  } catch (e) {
    ElMessage.error('交易请求失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.trade-panel-container { width: 340px; flex-shrink: 0; }
.quick-btns { display: flex; gap: 5px; margin-top: 8px; }
.quick-btns .el-button { flex: 1; }
.trade-btn { width: 100%; margin-top: 15px; font-weight: bold; }
.buy-btn { background-color: #f56c6c; border-color: #f56c6c; }
.sell-btn { background-color: #67c23a; border-color: #67c23a; }
.asset-info { margin-top: 10px; color: #666; font-size: 13px; background: #f1f5f9; padding: 8px; border-radius: 4px; }
.text-danger { color: #f56c6c; font-weight: bold; }
.price-hint { font-size: 12px; color: #999; margin-top: 4px; }
</style>