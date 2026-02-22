<template>
  <el-card shadow="never" class="position-card">
    <template #header>
      <div class="card-header">
        <span class="title">当前持仓</span>
        </div>
    </template>

    <el-table :data="tableData" style="width: 100%" v-loading="loading" stripe empty-text="暂无持仓">
      <el-table-column label="股票名称" min-width="140">
        <template #default="scope">
          <div class="stock-info" @click="goToStock(scope.row.stock_code)">
            <span class="name">{{ scope.row.stock_name }}</span>
            <span class="code">{{ scope.row.stock_code }}</span>
          </div>
        </template>
      </el-table-column>

      <el-table-column prop="volume" label="持仓/可用" width="120">
        <template #default="scope">
          {{ scope.row.volume }}
          </template>
      </el-table-column>

      <el-table-column label="现价/成本" width="140">
         <template #default="scope">
           <div class="price-col">
             <span :class="getPriceClass(scope.row.profit)">{{ formatNumber(scope.row.current_price) }}</span>
             <span class="sub-text">{{ formatNumber(scope.row.avg_price) }}</span>
           </div>
         </template>
      </el-table-column>

      <el-table-column label="市值" width="140">
        <template #default="scope">
          ¥ {{ formatNumber(scope.row.market_value) }}
        </template>
      </el-table-column>

      <el-table-column label="浮动盈亏" align="right">
        <template #default="scope">
           <div class="profit-col">
             <span :class="getPriceClass(scope.row.profit)">
               {{ scope.row.profit > 0 ? '+' : ''}}{{ formatNumber(scope.row.profit) }}
             </span>
             <span :class="getPriceClass(scope.row.profit_rate)" class="rate-tag">
               {{ scope.row.profit_rate > 0 ? '+' : ''}}{{ scope.row.profit_rate.toFixed(2) }}%
             </span>
           </div>
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'
import { useRouter } from 'vue-router'

const router = useRouter()
const loading = ref(false)
const tableData = ref([])

const getApi = () => {
    return axios.create({
        baseURL: 'http://127.0.0.1:8000/',
        headers: { 'Authorization': `Token ${localStorage.getItem('token')}` }
    })
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
    router.push({ name: 'stock-detail', params: { code } })
}

// 暴露给父组件调用的刷新方法
const fetchData = async () => {
  // 不显示 loading 以免轮询时闪烁，或者仅首次显示
  // loading.value = true
  try {
    const api = getApi()
    const res = await api.get('api/trade/positions/').catch(() => null)
    if (res && res.data.code === 200) {
      tableData.value = res.data.data
    }
  } catch (e) {
    console.error("获取持仓失败", e)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchData()
})

defineExpose({ fetchData })
</script>

<style scoped>
.position-card { border: none; box-shadow: 0 2px 12px rgba(0,0,0,0.05); margin-bottom: 20px; border-radius: 8px;}
.card-header { display: flex; justify-content: space-between; align-items: center; }
.title { font-weight: bold; font-size: 16px; border-left: 4px solid #409EFF; padding-left: 10px; color: #333; }
.stock-info { display: flex; flex-direction: column; cursor: pointer; }
.stock-info .name { font-weight: bold; color: #303133; }
.stock-info .code { font-size: 12px; color: #909399; }
.price-col { display: flex; flex-direction: column; }
.sub-text { font-size: 12px; color: #999; }
.profit-col { display: flex; flex-direction: column; align-items: flex-end; }
.rate-tag { font-size: 12px; margin-top: 2px; }
.up { color: #f56c6c; }
.down { color: #67c23a; }
</style>