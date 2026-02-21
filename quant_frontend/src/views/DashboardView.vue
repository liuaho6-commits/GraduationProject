<template>
  <div class="dashboard-container">
    <el-card class="asset-panel-card" shadow="never" v-loading="loading">
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
          <el-button type="primary" size="small" @click="openTransferDialog">银证转账</el-button>
        </el-col>
      </el-row>
    </el-card>

    <div class="chart-section">
      <PerformanceChart :user-data="userData" />
    </div>

    <div class="table-section">
      <el-card shadow="never">
        <template #header>
          <div class="card-header">
            <span class="title">近期成交记录</span>
            <el-button type="primary" link @click="manualRefresh">刷新</el-button>
          </div>
        </template>

        <el-table :data="recentOrders" style="width: 100%" v-loading="tableLoading" stripe>
          <el-table-column prop="order_time" label="成交时间" width="180">
            <template #default="scope">
              {{ formatTime(scope.row.order_time) }}
            </template>
          </el-table-column>

          <el-table-column label="股票代码" width="120">
            <template #default="scope">
              <span class="stock-link" @click="goToStock(scope.row.stock_code)">
                {{ scope.row.stock_code }}
              </span>
            </template>
          </el-table-column>

          <el-table-column prop="direction" label="方向" width="100">
            <template #default="scope">
              <el-tag :type="scope.row.direction === 'buy' ? 'danger' : 'success'" effect="dark">
                {{ scope.row.direction === 'buy' ? '买入' : '卖出' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="price" label="成交价格">
            <template #default="scope">¥ {{ formatNumber(scope.row.price) }}</template>
          </el-table-column>
          <el-table-column prop="volume" label="成交数量" />
          <el-table-column prop="status" label="状态" width="100">
            <template #default="scope">
               <el-tag type="success">已成交</el-tag>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </div>

    <el-dialog v-model="transferDialogVisible" title="银证转账" width="400px">
      <el-form label-position="top">
        <el-form-item label="操作类型">
          <el-radio-group v-model="transferType">
            <el-radio-button value="deposit">转入 (充值)</el-radio-button>
            <el-radio-button value="withdraw">转出 (提现)</el-radio-button>
          </el-radio-group>
        </el-form-item>

        <el-form-item :label="transferType === 'deposit' ? '转入金额' : '转出金额'">
           <el-input v-model="transferAmount" type="number" placeholder="请输入金额" >
             <template #prefix>¥</template>
           </el-input>
           <div class="balance-hint" v-if="transferType === 'withdraw'">
             可转出余额: ¥ {{ formatNumber(userData.balance) }}
           </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="transferDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleTransfer">确认{{ transferType === 'deposit' ? '转入' : '转出' }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue' // 引入 computed 和 onUnmounted
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import PerformanceChart from '../components/PerformanceChart.vue'

const router = useRouter()
const loading = ref(true)      // 首次加载的 loading
const tableLoading = ref(false) // 表格单独的 loading
const timer = ref(null)        // 定时器引用

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
const transferDialogVisible = ref(false)
const transferAmount = ref('')
const transferType = ref('deposit')

// === 新增：计算收益率 ===
const totalReturnRate = computed(() => {
    const initial = userData.value.initial_capital || 1 // 防止除以0
    const profit = userData.value.total_profit || 0
    const rate = (profit / initial) * 100
    return (rate > 0 ? '+' : '') + rate.toFixed(2) + '%'
})

const dailyReturnRate = computed(() => {
    // 简单估算：日收益率 = 日收益 / (当前资产 - 日收益)  即相对于昨天的资产
    const currentAssets = userData.value.total_assets || 0
    const dailyProfit = userData.value.daily_profit || 0
    const yesterdayAssets = currentAssets - dailyProfit
    
    if (yesterdayAssets <= 0) return '0.00%'
    const rate = (dailyProfit / yesterdayAssets) * 100
    return (rate > 0 ? '+' : '') + rate.toFixed(2) + '%'
})
// =======================

const getApi = () => {
    return axios.create({
        baseURL: 'http://127.0.0.1:8000/',
        headers: { 'Authorization': `Token ${localStorage.getItem('token')}` }
    })
}

const formatTime = (timeStr) => {
    if (!timeStr) return '--'
    return timeStr.replace('T', ' ').split('.')[0]
}

const formatNumber = (num) => {
    return Number(num || 0).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})
}

const getPriceClass = (val) => {
    if (val > 0) return 'up'
    if (val < 0) return 'down'
    return ''
}

const goToStock = (code) => {
    if(code) router.push({ name: 'stock-detail', params: { code: code } })
}

const openTransferDialog = () => {
    transferType.value = 'deposit'
    transferAmount.value = ''
    transferDialogVisible.value = true
}

// 手动刷新专用（带 loading）
const manualRefresh = () => {
    loading.value = true
    fetchDashboardData().finally(() => {
        loading.value = false
    })
}

const fetchDashboardData = async () => {
    // 注意：这里不要写 loading.value = true，否则轮询时界面会一直闪烁
    const api = getApi()
    try {
        // 1. 获取用户信息
        const userRes = await api.get('api/users/info/').catch(() => api.get('users/api/info/'))
        if (userRes && userRes.data.code === 200) {
            userData.value = userRes.data.data
            
            // 核心修正：仅重新计算总盈亏，不篡改日盈亏
            const assets = parseFloat(userData.value.total_assets) || 0
            const initial = parseFloat(userData.value.initial_capital) || 200000 
            
            // 强制统一总收益口径：(当前资产 - 初始本金)
            userData.value.total_profit = assets - initial
            
            // ⚠️ 以前这里有个错误的 if 判断把 daily_profit 设为 0，现在已删除
        }

        // 2. 获取交易记录 (静默刷新，不阻塞)
        const ordersRes = await api.get('api/trade/orders/').catch(() => null)
        if (ordersRes && ordersRes.data.code === 200) {
            recentOrders.value = ordersRes.data.data || []
        }
    } catch (e) {
        if (e.response && e.response.status === 401) {
             // 如果是轮询时 token 过期，清除定时器并跳转
             clearInterval(timer.value)
             router.push('/login')
        }
        console.error('Data sync failed:', e)
    }
}

const handleTransfer = async () => {
    const amount = parseFloat(transferAmount.value)
    if (!amount || amount <= 0) return ElMessage.warning('请输入有效的金额')

    let finalAmount = transferType.value === 'withdraw' ? -amount : amount
    if (transferType.value === 'withdraw' && amount > userData.value.balance) {
        return ElMessage.error('可用余额不足')
    }

    try {
        const res = await getApi().post('trade/api/transfer/', { amount: finalAmount })
        if (res.data.code === 200) {
            ElMessage.success('操作成功')
            transferDialogVisible.value = false
            manualRefresh() // 转账成功后立即手动刷新一次
        } else {
            ElMessage.error(res.data.msg || '操作失败')
        }
    } catch (e) {
        ElMessage.error('请求失败')
    }
}

// 生命周期管理
onMounted(() => {
    // 首次加载
    fetchDashboardData().finally(() => {
        loading.value = false // 首次加载完成后取消 loading 遮罩
    })

    // 开启轮询：每 3000ms (3秒) 更新一次数据
    timer.value = setInterval(() => {
        fetchDashboardData()
    }, 3000)
})

// 页面销毁前清理定时器
onUnmounted(() => {
    if (timer.value) {
        clearInterval(timer.value)
        timer.value = null
    }
})
</script>

<style scoped>
.dashboard-container { padding: 20px; background-color: #f8f9fa; min-height: 100vh; }
.asset-panel-card { border-radius: 12px; margin-bottom: 20px; border: none; box-shadow: 0 4px 12px rgba(0,0,0,0.05) !important; }
.asset-main { display: flex; justify-content: space-between; align-items: center; padding: 10px 20px; }
.total-value { font-size: 36px; font-weight: 700; margin: 8px 0; color: #1a1a1a; font-family: 'DIN Alternate', sans-serif; }
.profit-summary { display: flex; gap: 40px; }
.profit-item { display: flex; flex-direction: column; align-items: flex-end; }
.profit-item span:nth-child(2) { font-size: 20px; font-weight: 600; margin-top: 4px; display: flex; align-items: baseline; gap: 5px; }
.rate-text { font-size: 13px; font-weight: 400; opacity: 0.8; } /* 新增样式 */
.asset-grid { padding: 10px 20px; }
.grid-item { display: flex; flex-direction: column; gap: 8px; }
.grid-item .value { font-size: 18px; font-weight: 600; color: #2c3e50; }
.action-col { display: flex; align-items: center; justify-content: flex-end; }
.label { font-size: 13px; color: #909399; }
.up { color: #f56c6c; }
.down { color: #67c23a; }
.chart-section { margin-bottom: 20px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.title { font-weight: bold; font-size: 16px; }
.stock-link { color: #409EFF; cursor: pointer; font-weight: 500; }
.stock-link:hover { text-decoration: underline; }
.balance-hint { font-size: 12px; color: #909399; margin-top: 5px; }
</style>