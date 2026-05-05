<template>
  <el-card shadow="never" class="index-board">
    <template #header>
      <div class="board-header">
        <div>
          <div class="title">大盘指数</div>
          <div class="subtitle">截至 {{ latestDate || '--' }}</div>
        </div>
        <el-button :icon="Refresh" circle plain :loading="loading" @click="fetchIndices" />
      </div>
    </template>

    <el-row :gutter="16">
      <el-col v-for="item in indices" :key="item.code" :xs="24" :sm="12" :lg="6">
        <div class="index-item" @click="goToIndex(item.code)">
          <div class="item-head">
            <div>
              <div class="name">{{ item.name }}</div>
              <div class="code">{{ item.code }}</div>
            </div>
            <el-icon class="arrow"><ArrowRight /></el-icon>
          </div>
          <div class="price" :class="getChangeClass(item.change)">
            {{ formatPrice(item.price) }}
          </div>
          <div class="metrics">
            <span :class="getChangeClass(item.change)">
              {{ item.change > 0 ? '+' : '' }}{{ formatPrice(item.change) }}%
            </span>
            <span :class="getChangeClass(item.change)">
              {{ item.change_amount > 0 ? '+' : '' }}{{ formatPrice(item.change_amount) }}
            </span>
          </div>
          <div class="amount">成交额 {{ formatAmount(item.amount) }}</div>
        </div>
      </el-col>
    </el-row>
  </el-card>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { ArrowRight, Refresh } from '@element-plus/icons-vue'

const router = useRouter()
const loading = ref(false)
const indices = ref([])

const api = axios.create({
  baseURL: 'http://127.0.0.1:8000/',
  headers: { Authorization: `Token ${localStorage.getItem('token')}` }
})

const latestDate = computed(() => indices.value[0]?.date || '')

const fetchIndices = async () => {
  loading.value = true
  try {
    const res = await api.get('stocks/api/indices/')
    if (res.data.code === 200) {
      indices.value = res.data.data || []
    }
  } catch (err) {
    console.error(err)
    ElMessage.error('大盘指数获取失败')
  } finally {
    loading.value = false
  }
}

const goToIndex = (code) => {
  router.push(`/index/${code}`)
}

const getChangeClass = (value) => {
  if (value > 0) return 'is-up'
  if (value < 0) return 'is-down'
  return 'is-flat'
}

const formatPrice = (value) => Number(value || 0).toFixed(2)

const formatAmount = (value) => {
  const num = Number(value || 0)
  if (num >= 100000000) return `${(num / 100000000).toFixed(2)} 亿`
  if (num >= 10000) return `${(num / 10000).toFixed(2)} 万`
  return num.toFixed(0)
}

onMounted(fetchIndices)
</script>

<style scoped>
.index-board {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  margin-bottom: 16px;
}

.board-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.title {
  color: #0f172a;
  font-size: 18px;
  font-weight: 700;
}

.subtitle {
  color: #64748b;
  font-size: 12px;
  margin-top: 2px;
}

.index-item {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  cursor: pointer;
  min-height: 150px;
  padding: 16px;
  transition: border-color 0.2s, box-shadow 0.2s, transform 0.2s;
}

.index-item:hover {
  border-color: #93c5fd;
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.08);
  transform: translateY(-2px);
}

.item-head {
  align-items: flex-start;
  display: flex;
  justify-content: space-between;
  min-height: 38px;
}

.name {
  color: #1e293b;
  font-size: 15px;
  font-weight: 700;
}

.code {
  color: #94a3b8;
  font-family: "Roboto Mono", monospace;
  font-size: 12px;
  margin-top: 3px;
}

.arrow {
  color: #94a3b8;
  font-size: 16px;
}

.price {
  font-family: "Roboto Mono", monospace;
  font-size: 26px;
  font-weight: 800;
  line-height: 34px;
  margin-top: 14px;
}

.metrics {
  display: flex;
  font-family: "Roboto Mono", monospace;
  font-size: 13px;
  font-weight: 700;
  gap: 12px;
  margin-top: 6px;
}

.amount {
  color: #64748b;
  font-size: 12px;
  margin-top: 12px;
}

.is-up { color: #dc2626; }
.is-down { color: #16a34a; }
.is-flat { color: #475569; }
</style>
