<template>
  <div class="market-container">
    <MarketIndexBoard />

    <el-card shadow="never" class="main-card">
      <template #header>
        <MarketHeader
          v-model:activeTab="activeTab"
          :market-time="marketTime"
          @tab-change="handleTabChange"
          @refresh="handleManualRefresh"
        />
      </template>

      <StockTable
        :data="tableData"
        :loading="loading"
        :total="total"
        :current-page="currentPage"
        :active-tab="activeTab"
        :favorite-codes="favoriteCodes"
        @toggle-favorite="toggleFavorite"
        @sort-change="handleSortChange"
        @page-change="handlePageChange"
      />
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'

// 引入子组件
import MarketHeader from '../components/MarketHeader.vue'
import MarketIndexBoard from '../components/MarketIndexBoard.vue'
import StockTable from '../components/StockTable.vue'

const token = localStorage.getItem('token')
const api = axios.create({
  baseURL: 'http://127.0.0.1:8000/',
  headers: { 'Authorization': `Token ${token}` }
})

// 状态管理
const activeTab = ref('all')
const tableData = ref([])
const marketTime = ref('')
const loading = ref(false)
const total = ref(0)
const currentPage = ref(1)
const favoriteCodes = ref(new Set()) // 使用 Set 来快速判断是否收藏
let refreshTimer = null
let tableRequestSeq = 0
let loadingRequestSeq = 0

// 排序状态
const sortProp = ref('')
const sortOrder = ref('')

// --- 核心数据获取逻辑 ---

const fetchMarketData = async (page = 1, forceRefresh = false, silent = false) => {
  const requestSeq = ++tableRequestSeq
  if (!silent) {
    loadingRequestSeq = requestSeq
    loading.value = true
  }

  try {
    let url = `stocks/api/market/?page=${page}`
    if (sortProp.value && sortOrder.value) {
      url += `&sort_prop=${sortProp.value}&sort_order=${sortOrder.value}`
    }
    if (forceRefresh) {
      url += `&refresh=true`
    }

    const res = await api.get(url)
    if (activeTab.value !== 'all' || requestSeq !== tableRequestSeq) return

    tableData.value = res.data.results
    total.value = res.data.count
    currentPage.value = page

    if (tableData.value.length > 0) {
      marketTime.value = tableData.value[0].date
    }

    // 获取数据后，顺便更新一下收藏状态（静默）
    if (!silent) {
      await fetchFavoritesList(false)
    }

    if (forceRefresh && requestSeq === tableRequestSeq) ElMessage.success('已刷新')
  } catch (err) {
    if (!silent && loadingRequestSeq === requestSeq) ElMessage.error('获取失败')
    console.error(err)
  } finally {
    if (!silent && loadingRequestSeq === requestSeq) loading.value = false
  }
}

const sortRows = (rows) => {
  if (!sortProp.value || !sortOrder.value) return rows

  const direction = sortOrder.value === 'descending' ? -1 : 1
  return [...rows].sort((a, b) => {
    const aVal = a[sortProp.value]
    const bVal = b[sortProp.value]

    if (typeof aVal === 'number' && typeof bVal === 'number') {
      return (aVal - bVal) * direction
    }

    return String(aVal ?? '').localeCompare(String(bVal ?? ''), 'zh-CN') * direction
  })
}

const fetchFavoritesList = async (updateTable = true, silent = false) => {
  const requestSeq = updateTable ? ++tableRequestSeq : tableRequestSeq
  if (updateTable && !silent) {
    loadingRequestSeq = requestSeq
    loading.value = true
  }

  try {
    const res = await api.get('api/users/favorites/')
    const list = res.data.data
    // 更新 Set
    favoriteCodes.value = new Set(list.map(item => item.stock))

    // 如果当前在看自选股 Tab，直接用这个数据渲染表格
    if (updateTable) {
      if (activeTab.value !== 'favorites' || requestSeq !== tableRequestSeq) return

      const rows = list.map(item => ({
        code: item.stock,
        name: item.name,
        price: item.price,
        date: item.add_time,
        change: item.change
      }))

      tableData.value = sortRows(rows)
      total.value = rows.length
      currentPage.value = 1
    }
  } catch (err) {
    console.error(err)
  } finally {
    if (updateTable && !silent && loadingRequestSeq === requestSeq) loading.value = false
  }
}

// --- 事件处理 ---

const handleSortChange = ({ prop, order }) => {
  sortProp.value = prop || ''
  sortOrder.value = order || ''

  if (activeTab.value === 'all') {
    fetchMarketData(1, false, false)
  } else {
    tableData.value = sortRows(tableData.value)
  }
}

const handleManualRefresh = () => {
  if (activeTab.value === 'all') {
    fetchMarketData(currentPage.value, true, false)
  } else {
    fetchFavoritesList(true, false)
  }
}

const handlePageChange = (val) => fetchMarketData(val, false, false)

const handleTabChange = (tab) => {
  activeTab.value = tab
  // 切换 tab 时重置排序或页码逻辑可视需求而定
  if (tab === 'all') {
    fetchMarketData(1, false, false)
  } else {
    fetchFavoritesList(true, false)
  }
}

const toggleFavorite = async (row) => {
  const code = row.code
  try {
    if (favoriteCodes.value.has(code)) {
      // 取消收藏
      await api.delete('api/users/favorites/', { data: { code } })
      ElMessage.info(`取消关注 ${code}`)
      const nextFavorites = new Set(favoriteCodes.value)
      nextFavorites.delete(code)
      favoriteCodes.value = nextFavorites
      // 如果在自选股列表，直接移除该行
      if (activeTab.value === 'favorites') {
        tableData.value = tableData.value.filter(item => item.code !== code)
        total.value = tableData.value.length
      }
    } else {
      // 添加收藏
      await api.post('api/users/favorites/', { code })
      ElMessage.success(`关注 ${code}`)
      favoriteCodes.value = new Set([...favoriteCodes.value, code])
    }
  } catch (err) {
    ElMessage.error('操作失败')
  }
}

// --- 生命周期 ---

onMounted(() => {
  fetchMarketData(1, false, false)

  // 自动轮询
  refreshTimer = setInterval(() => {
    if (loading.value) return

    if (activeTab.value === 'all') {
      fetchMarketData(currentPage.value, false, true) // silent refresh
    } else {
      fetchFavoritesList(true, true) // silent refresh
    }
  }, 3000)
})

onBeforeUnmount(() => {
  if (refreshTimer) clearInterval(refreshTimer)
})
</script>

<style scoped>
.market-container { padding: 24px; background-color: #f8fafc; min-height: 100vh; }
.main-card { border-radius: 12px; border: 1px solid #e2e8f0; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
</style>
