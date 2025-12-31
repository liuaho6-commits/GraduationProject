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
                <el-icon><Clock /></el-icon> 行情时间: {{ marketTime }}
              </span>
            </transition>
            <el-divider direction="vertical" />
            <el-button type="primary" :icon="Refresh" circle @click="handleManualRefresh" title="手动刷新" />
          </div>
        </div>
      </template>

      <el-table
        :data="tableData"
        v-loading="loading"
        style="width: 100%"
        :header-cell-style="{ background: '#f8fafc', color: '#64748b' }"
        @sort-change="handleSortChange"
      >
        <el-table-column width="50" align="center">
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

        <el-table-column prop="code" label="代码" width="110" sortable="custom">
          <template #default="scope">
            <el-tooltip content="点击复制" placement="top" :show-after="500">
              <el-tag
                type="info"
                effect="plain"
                class="code-tag"
                @click.stop="copyCode(scope.row.code)"
              >
                {{ scope.row.code }}
              </el-tag>
            </el-tooltip>
          </template>
        </el-table-column>

        <el-table-column prop="name" label="名称" width="120">
          <template #default="scope">
            <span class="stock-name-link" @click.stop="goToDetail(scope.row.code)">
              {{ scope.row.name }}
            </span>
          </template>
        </el-table-column>

        <el-table-column prop="price" label="最新价" width="100" align="right" sortable="custom">
          <template #default="scope">
            <span class="price-font">{{ scope.row.price.toFixed(2) }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="change" label="日涨跌" width="110" align="right" sortable="custom">
          <template #default="scope">
            <span class="percent-font" :class="getColorClass(scope.row.change)">
              {{ scope.row.change > 0 ? '+' : '' }}{{ scope.row.change }}%
            </span>
          </template>
        </el-table-column>

        <el-table-column prop="change_1w" label="近1周" width="110" align="right" sortable="custom">
          <template #default="scope">
            <span class="percent-font" :class="getColorClass(scope.row.change_1w)">
              {{ scope.row.change_1w > 0 ? '+' : '' }}{{ scope.row.change_1w }}%
            </span>
          </template>
        </el-table-column>

        <el-table-column prop="change_1y" label="近1年" width="110" align="right" sortable="custom">
          <template #default="scope">
            <span class="percent-font" :class="getColorClass(scope.row.change_1y)">
              {{ scope.row.change_1y > 0 ? '+' : '' }}{{ scope.row.change_1y }}%
            </span>
          </template>
        </el-table-column>

        <el-table-column prop="change_2y" label="近2年" width="110" align="right" sortable="custom">
          <template #default="scope">
            <span class="percent-font" :class="getColorClass(scope.row.change_2y)">
              {{ scope.row.change_2y > 0 ? '+' : '' }}{{ scope.row.change_2y }}%
            </span>
          </template>
        </el-table-column>

        <el-table-column prop="change_3y" label="近3年" min-width="110" align="right" sortable="custom">
          <template #default="scope">
            <span class="percent-font" :class="getColorClass(scope.row.change_3y)">
              {{ scope.row.change_3y > 0 ? '+' : '' }}{{ scope.row.change_3y }}%
            </span>
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
         <p v-if="activeTab === 'favorites'">暂无自选股，快去全市场添加吧！</p>
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

const getColorClass = (val) => {
  if (val > 0) return 'text-red'
  if (val < 0) return 'text-green'
  return 'text-gray'
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
        // 自选股列表默认0，直到下次全量刷新或单独接口支持
        change: 0, change_1w: 0, change_1y: 0, change_2y: 0, change_3y: 0
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
.market-container { padding: 20px; background-color: #f1f5f9; min-height: 100vh; }
.main-card { border-radius: 8px; overflow: hidden; border: none; }
.header-row { display: flex; justify-content: space-between; align-items: center; height: 40px; }
.header-left { flex: 1; }
.header-right { display: flex; align-items: center; gap: 15px; }
.market-time {
    font-size: 13px;
    color: #909399;
    font-family: 'Roboto Mono', monospace;
    display: flex;
    align-items: center;
    gap: 6px;
}
.code-tag {
    cursor: pointer;
    font-family: 'Roboto Mono', monospace;
    font-weight: 500;
    transition: all 0.2s;
}
.code-tag:hover { background-color: #e2e8f0; color: #334155; }
.stock-name-link {
    color: #1e293b;
    font-weight: 600;
    cursor: pointer;
    transition: color 0.2s;
}
.stock-name-link:hover { color: #409EFF; }
.price-font { font-family: 'Roboto Mono', monospace; font-weight: 600; color: #333; }
.percent-font { font-family: 'Roboto Mono', monospace; font-weight: 600; }
.text-red { color: #f56c6c; }
.text-green { color: #00C853; }
.text-gray { color: #909399; }
.star-icon { font-size: 18px; cursor: pointer; color: #cbd5e1; transition: transform 0.2s, color 0.2s; }
.star-icon:hover { transform: scale(1.1); }
.star-icon.is-active { color: #f59e0b; }
.pagination-area { margin-top: 25px; display: flex; justify-content: center; }
.empty-state { text-align: center; padding: 40px; color: #909399; }
</style>