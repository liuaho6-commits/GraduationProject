<template>
  <div class="market-container">
    <el-card shadow="never" class="main-card">
      <template #header>
        <div class="header-row">
          <div class="header-left">
            <el-tabs v-model="activeTab" @tab-change="handleTabChange" class="no-border-tabs">
              <el-tab-pane label="全市场行情" name="all"></el-tab-pane>
              <el-tab-pane label="我的自选股" name="favorites"></el-tab-pane>
            </el-tabs>
          </div>

          <div class="header-right">
            <transition name="el-fade-in">
              <span v-if="marketTime" class="market-time">
                <el-icon><Clock /></el-icon> {{ marketTime }}
              </span>
            </transition>
            <el-divider direction="vertical" />
            <el-button type="primary" :icon="Refresh" circle plain @click="handleManualRefresh" title="手动刷新" />
          </div>
        </div>
      </template>

      <el-table
        :data="tableData"
        v-loading="loading"
        style="width: 100%"
        :header-cell-style="{ background: '#f8fafc', color: '#475569', fontWeight: '600', height: '50px' }"
        :row-style="{ height: '55px' }"
        stripe
        highlight-current-row
        @sort-change="handleSortChange"
      >
        <el-table-column width="60" align="center">
          <template #default="scope">
            <el-icon
              class="star-icon"
              :class="{ 'is-active': isFavorite(scope.row.code) }"
              @click.stop="toggleFavorite(scope.row)"
            >
              <StarFilled v-if="isFavorite(scope.row.code)" />
              <Star v-else />
            </el-icon>
          </template>
        </el-table-column>

        <el-table-column prop="code" label="代码" width="100" sortable="custom">
          <template #default="scope">
            <el-tooltip content="点击复制" placement="top" :show-after="500">
              <span class="code-text" @click.stop="copyCode(scope.row.code)">
                {{ scope.row.code }}
              </span>
            </el-tooltip>
          </template>
        </el-table-column>

        <el-table-column prop="name" label="名称" min-width="180">
          <template #default="scope">
            <span class="stock-name-link" @click.stop="goToDetail(scope.row.code)">
              {{ scope.row.name }}
            </span>
          </template>
        </el-table-column>

        <el-table-column prop="price" label="最新价" width="140" align="right" sortable="custom">
          <template #default="scope">
            <span class="price-font">{{ scope.row.price.toFixed(2) }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="change" label="涨跌幅" width="140" align="right" sortable="custom">
          <template #default="scope">
            <div class="change-tag" :class="getChangeClass(scope.row.change)">
              {{ scope.row.change > 0 ? '+' : '' }}{{ scope.row.change }}%
            </div>
          </template>
        </el-table-column>

      </el-table>

      <div class="pagination-area" v-if="activeTab === 'all' && tableData.length > 0">
        <el-pagination
          background
          layout="prev, pager, next"
          :total="total"
          :page-size="20"
          :current-page="currentPage"
          @current-change="handlePageChange"
        />
      </div>

      <div v-else-if="tableData.length === 0 && !loading" class="empty-state">
         <div class="empty-icon">📊</div>
         <p v-if="activeTab === 'favorites'">暂无自选股，去市场看看吧</p>
         <p v-else>暂无数据</p>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import axios from 'axios'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Refresh, Star, StarFilled, Clock } from '@element-plus/icons-vue'

const router = useRouter()
const token = localStorage.getItem('token')
const api = axios.create({
  baseURL: 'http://127.0.0.1:8000/',
  headers: { 'Authorization': `Token ${token}` }
})

const activeTab = ref('all')
const tableData = ref([])
const marketTime = ref('')
const loading = ref(false)
const total = ref(0)
const currentPage = ref(1)
const favoriteCodes = ref(new Set())
let refreshTimer = null

// 排序状态
const sortProp = ref('')
const sortOrder = ref('')

// 🟢 样式辅助函数
const getChangeClass = (val) => {
  if (val > 0) return 'tag-red'
  if (val < 0) return 'tag-green'
  return 'tag-gray'
}

const fetchMarketData = async (page = 1, forceRefresh = false, silent = false) => {
  if (!silent) loading.value = true

  try {
    let url = `stocks/api/market/?page=${page}`
    if (sortProp.value && sortOrder.value) {
      url += `&sort_prop=${sortProp.value}&sort_order=${sortOrder.value}`
    }
    if (forceRefresh) {
      url += `&refresh=true`
    }

    const res = await api.get(url)
    tableData.value = res.data.results
    total.value = res.data.count
    currentPage.value = page

    if (tableData.value.length > 0) {
        marketTime.value = tableData.value[0].date
    }

    if (!silent) {
        await fetchFavoritesList(false)
    }

    if (forceRefresh) ElMessage.success('已刷新')
  } catch (err) {
    if (!silent) ElMessage.error('获取失败')
  } finally {
    if (!silent) loading.value = false
  }
}

const handleSortChange = ({ prop, order }) => {
  sortProp.value = prop
  sortOrder.value = order
  fetchMarketData(1, false, false)
}

const handleManualRefresh = () => {
  if (activeTab.value === 'all') {
    fetchMarketData(currentPage.value, true, false)
  } else {
    fetchFavoritesList(true)
  }
}

const handlePageChange = (val) => fetchMarketData(val, false, false)

const fetchFavoritesList = async (updateTable = true) => {
  if (updateTable) loading.value = true
  try {
    const res = await api.get('api/users/favorites/')
    const list = res.data.data
    favoriteCodes.value = new Set(list.map(item => item.stock))
    if (updateTable) {
      tableData.value = list.map(item => ({
        code: item.stock,
        name: item.name,
        price: item.price,
        date: item.add_time,
        change: item.change
      }))
    }
  } catch (err) {
    console.error(err)
  } finally {
    if (updateTable) loading.value = false
  }
}

const isFavorite = (code) => favoriteCodes.value.has(code)

const handleTabChange = (tab) => {
  if (tab === 'all') fetchMarketData(1, false, false)
  else fetchFavoritesList(true)
}

const toggleFavorite = async (row) => {
  const code = row.code
  try {
    if (isFavorite(code)) {
      await api.delete('api/users/favorites/', { data: { code } })
      ElMessage.info(`取消关注 ${code}`)
      favoriteCodes.value.delete(code)
      if (activeTab.value === 'favorites') {
        tableData.value = tableData.value.filter(item => item.code !== code)
      }
    } else {
      await api.post('api/users/favorites/', { code })
      ElMessage.success(`关注 ${code}`)
      favoriteCodes.value.add(code)
    }
  } catch (err) {
    ElMessage.error('操作失败')
  }
}

const goToDetail = (code) => router.push(`/stock/${code}`)

const copyCode = (code) => {
  navigator.clipboard.writeText(code).then(() => {
    ElMessage.success(`已复制 ${code}`)
  })
}

onMounted(() => {
  fetchMarketData(1, false, false)

  refreshTimer = setInterval(() => {
      if (activeTab.value === 'all') {
          fetchMarketData(currentPage.value, false, true)
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

/* Header */
.header-row { display: flex; justify-content: space-between; align-items: center; padding-bottom: 2px; }
.header-right { display: flex; align-items: center; gap: 12px; }
.market-time {
    font-size: 13px;
    color: #64748b;
    font-family: 'Roboto Mono', monospace;
    display: flex;
    align-items: center;
    gap: 6px;
    background: #f1f5f9;
    padding: 4px 10px;
    border-radius: 6px;
}

/* Table Content */
.code-text {
    font-family: 'Roboto Mono', monospace;
    color: #64748b;
    font-weight: 500;
    cursor: pointer;
    transition: color 0.2s;
}
.code-text:hover { color: #3b82f6; }

.stock-name-link {
    color: #1e293b;
    font-weight: 600;
    font-size: 15px;
    cursor: pointer;
    transition: color 0.2s;
}
.stock-name-link:hover { color: #3b82f6; }

.price-font {
    font-family: 'Roboto Mono', monospace;
    font-weight: 700;
    color: #0f172a;
    font-size: 15px;
}

/* 🟢 涨跌幅 Tag 样式 */
.change-tag {
    display: inline-block;
    padding: 4px 12px;
    border-radius: 6px;
    font-family: 'Roboto Mono', monospace;
    font-weight: 600;
    font-size: 14px;
    min-width: 70px;
    text-align: center;
}
.tag-red { color: #dc2626; background-color: #fee2e2; }
.tag-green { color: #16a34a; background-color: #dcfce7; }
.tag-gray { color: #64748b; background-color: #f1f5f9; }

/* Icon */
.star-icon { font-size: 18px; cursor: pointer; color: #cbd5e1; transition: all 0.2s; }
.star-icon:hover { transform: scale(1.2); }
.star-icon.is-active { color: #f59e0b; }

/* Misc */
.pagination-area { margin-top: 30px; display: flex; justify-content: center; }
.empty-state { text-align: center; padding: 60px 0; color: #94a3b8; }
.empty-icon { font-size: 48px; margin-bottom: 16px; opacity: 0.5; }
</style>