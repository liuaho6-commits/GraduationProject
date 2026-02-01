<template>
  <div class="dashboard-container">
    <div class="stats-cards">
      <el-card shadow="hover" class="stat-card">
        <template #header><span class="card-title">总资产</span></template>
        <div class="card-value money" v-loading="loading">
            ¥ {{ formatNumber(totalAssets) }}
        </div>
        <div class="card-footer">
          日收益: <span :class="dayProfit >= 0 ? 'up' : 'down'">
            {{ dayProfit >= 0 ? '+' : '' }}{{ dayProfit }}
          </span>
        </div>
      </el-card>

      <el-card shadow="hover" class="stat-card">
        <template #header><span class="card-title">可用余额</span></template>
        <div class="card-value" v-loading="loading">
            ¥ {{ formatNumber(availableBalance) }}
        </div>
        <div class="card-footer">
          <el-button type="primary" link @click="openTransferDialog">银证转账</el-button>
        </div>
      </el-card>

      <el-card shadow="hover" class="stat-card">
        <template #header><span class="card-title">累计收益率</span></template>
        <div class="card-value" :class="totalReturn >= 0 ? 'up' : 'down'" v-loading="loading">
          {{ totalReturn }}%
        </div>
        <div class="card-footer">运行中策略: {{ activeStrategies }} 个</div>
      </el-card>
    </div>

    <div class="chart-section">
      <PerformanceChart />
    </div>

    <div class="table-section">
      <el-card shadow="never">
        <template #header>
          <div class="card-header">
            <span>近期交易记录</span>
            <el-button type="primary" link @click="fetchDashboardData">刷新</el-button>
          </div>
        </template>

        <el-table :data="recentOrders" style="width: 100%" v-loading="loading" stripe>
          <el-table-column prop="order_time" label="成交时间" width="180">
            <template #default="scope">
              {{ formatTime(scope.row.order_time) }}
            </template>
          </el-table-column>

          <el-table-column label="股票名称/代码" width="160">
            <template #default="scope">
              <span class="stock-link" @click="goToStock(scope.row.stock_code)">
                {{ scope.row.stock_name }}
                <span class="stock-code">({{ scope.row.stock_code }})</span>
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
          <el-table-column prop="price" label="成交均价">
            <template #default="scope">¥ {{ formatNumber(scope.row.price) }}</template>
          </el-table-column>
          <el-table-column prop="volume" label="成交数量" />
          <el-table-column prop="status" label="状态" width="100">
            <template #default="scope">
               <el-tag v-if="scope.row.status === 'filled' || scope.row.status === 'success'" type="success">已成交</el-tag>
               <el-tag v-else-if="scope.row.status === 'pending'" type="warning">待成交</el-tag>
               <el-tag v-else type="info">{{ scope.row.status }}</el-tag>
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
           <el-input v-model="transferAmount" type="number" placeholder="请输入正整数金额" >
             <template #prefix>¥</template>
           </el-input>
           <div class="balance-hint" v-if="transferType === 'withdraw'">
             可转出余额: ¥ {{ formatNumber(availableBalance) }}
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
import { ref, onMounted } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import PerformanceChart from '../components/PerformanceChart.vue'

const router = useRouter()
const loading = ref(true)
const totalAssets = ref(0)
const availableBalance = ref(0)
const dayProfit = ref(0)
const totalReturn = ref(0)
const activeStrategies = ref(0)
const recentOrders = ref([])

const transferDialogVisible = ref(false)
const transferAmount = ref('')
const transferType = ref('deposit')

// 动态获取 Token 的 API 实例
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
    if (num === undefined || num === null) return '0.00'
    return Number(num).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})
}

const goToStock = (code) => {
    if(code) router.push({ name: 'stock-detail', params: { code: code } })
}

const openTransferDialog = () => {
    transferType.value = 'deposit'
    transferAmount.value = ''
    transferDialogVisible.value = true
}

const fetchDashboardData = async () => {
    loading.value = true
    const api = getApi()
    try {
        let userRes = await api.get('api/users/info/').catch(() => null)
        if (!userRes) userRes = await api.get('users/api/info/').catch(() => null)

        if (userRes && userRes.data.code === 200) {
            const data = userRes.data.data || userRes.data
            availableBalance.value = parseFloat(data.balance || 0)
            totalAssets.value = parseFloat(data.total_assets || data.balance || 0)
        }

        const perfRes = await api.get('trade/api/performance/?type=daily').catch(() => null)
        if (perfRes && perfRes.data.code === 200 && perfRes.data.data.length > 0) {
            const history = perfRes.data.data
            const lastDay = history[history.length - 1]
            dayProfit.value = lastDay.day_profit || 0
            totalReturn.value = lastDay.total_return_rate || 0
        }

        const ordersRes = await api.get('api/trade/orders/').catch(() => null)
        if (ordersRes && ordersRes.data.code === 200) {
            recentOrders.value = ordersRes.data.data || []
        }
    } catch (e) {
        if (e.response && e.response.status === 401) router.push('/login')
    } finally {
        loading.value = false
    }
}

const handleTransfer = async () => {
    const amount = parseFloat(transferAmount.value)
    if (!amount || amount <= 0) {
        return ElMessage.warning('请输入有效的正数金额')
    }

    let finalAmount = amount
    if (transferType.value === 'withdraw') {
        if (amount > availableBalance.value) {
            return ElMessage.error('余额不足')
        }
        finalAmount = -amount
    }

    try {
        const api = getApi()
        const res = await api.post('trade/api/transfer/', { amount: finalAmount })
        if (res.data.code === 200) {
            ElMessage.success(transferType.value === 'deposit' ? '充值成功' : '提现成功')
            transferDialogVisible.value = false
            fetchDashboardData()
        } else {
            ElMessage.error(res.data.msg || '操作失败')
        }
    } catch (e) {
        ElMessage.error('网络请求失败')
    }
}

onMounted(() => {
    fetchDashboardData()
})
</script>

<style scoped>
.dashboard-container { padding: 20px; }
.stats-cards { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-bottom: 20px; }
.stat-card { border-radius: 8px; }
.card-title { font-size: 14px; color: #909399; }
.card-value { font-size: 28px; font-weight: bold; margin: 10px 0; color: #303133; }
.money { font-family: 'Helvetica Neue', sans-serif; }
.up { color: #f56c6c; }
.down { color: #67c23a; }
.card-footer { font-size: 12px; color: #606266; display: flex; justify-content: space-between; align-items: center; }
.chart-section { margin-top: 20px; margin-bottom: 20px; }
.table-section { margin-top: 20px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.stock-link { color: #409EFF; cursor: pointer; font-weight: 500; }
.stock-link:hover { text-decoration: underline; }
.stock-code { color: #999; font-size: 12px; margin-left: 4px; }
.balance-hint { font-size: 12px; color: #909399; margin-top: 5px; }
</style>