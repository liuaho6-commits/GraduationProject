<template>
  <el-card shadow="never">
    <template #header>
      <div class="card-header">
        <span class="title">近期成交记录</span>
        <el-button type="primary" link @click="$emit('refresh')" :loading="loading">刷新</el-button>
      </div>
    </template>

    <el-table :data="orders" style="width: 100%" v-loading="loading" stripe empty-text="暂无成交记录">
      <el-table-column prop="order_time" label="成交时间" width="180">
        <template #default="scope">
          {{ formatTime(scope.row.order_time) }}
        </template>
      </el-table-column>

      <el-table-column label="股票名称" width="140">
        <template #default="scope">
          <span class="stock-link" @click="goToStock(scope.row.stock_code)">
            {{ scope.row.stock_name || scope.row.stock_code }}
          </span>
          <span style="font-size: 12px; color: #999; margin-left: 5px;">{{ scope.row.stock_code }}</span>
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
</template>

<script setup>
import { useRouter } from 'vue-router'

const props = defineProps({
  orders: {
    type: Array,
    default: () => []
  },
  loading: {
    type: Boolean,
    default: false
  }
})

defineEmits(['refresh'])

const router = useRouter()

const formatTime = (timeStr) => {
  if (!timeStr) return '--'
  return timeStr.replace('T', ' ').split('.')[0]
}

const formatNumber = (num) => {
  return Number(num || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

const goToStock = (code) => {
  if (code) router.push({ name: 'stock-detail', params: { code: code } })
}
</script>

<style scoped>
.card-header { display: flex; justify-content: space-between; align-items: center; }
.title { font-weight: bold; font-size: 16px; }
.stock-link { color: #409EFF; cursor: pointer; font-weight: 500; }
.stock-link:hover { text-decoration: underline; }
</style>