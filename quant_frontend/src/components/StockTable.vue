<template>
  <div class="stock-table-container">
    <el-table
      :data="data"
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
            @click.stop="$emit('toggle-favorite', scope.row)"
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

    <div class="pagination-area" v-if="activeTab === 'all' && data.length > 0">
      <el-pagination
        background
        layout="prev, pager, next"
        :total="total"
        :page-size="20"
        :current-page="currentPage"
        @current-change="$emit('page-change', $event)"
      />
    </div>

    <div v-else-if="data.length === 0 && !loading" class="empty-state">
      <div class="empty-icon">📊</div>
      <p v-if="activeTab === 'favorites'">暂无自选股，去市场看看吧</p>
      <p v-else>暂无数据</p>
    </div>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Star, StarFilled } from '@element-plus/icons-vue'

const props = defineProps({
  data: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  total: { type: Number, default: 0 },
  currentPage: { type: Number, default: 1 },
  activeTab: { type: String, default: 'all' },
  favoriteCodes: { type: Set, default: () => new Set() } // 接收一个 Set 集合
})

const emit = defineEmits(['toggle-favorite', 'sort-change', 'page-change'])
const router = useRouter()

const isFavorite = (code) => props.favoriteCodes.has(code)

const getChangeClass = (val) => {
  if (val > 0) return 'tag-red'
  if (val < 0) return 'tag-green'
  return 'tag-gray'
}

const copyCode = (code) => {
  navigator.clipboard.writeText(code).then(() => {
    ElMessage.success(`已复制 ${code}`)
  })
}

const goToDetail = (code) => {
  router.push(`/stock/${code}`)
}

const handleSortChange = ({ prop, order }) => {
  emit('sort-change', { prop, order })
}
</script>

<style scoped>
/* Table Content Styles */
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

.star-icon { font-size: 18px; cursor: pointer; color: #cbd5e1; transition: all 0.2s; }
.star-icon:hover { transform: scale(1.2); }
.star-icon.is-active { color: #f59e0b; }

.pagination-area { margin-top: 30px; display: flex; justify-content: center; }
.empty-state { text-align: center; padding: 60px 0; color: #94a3b8; }
.empty-icon { font-size: 48px; margin-bottom: 16px; opacity: 0.5; }
</style>