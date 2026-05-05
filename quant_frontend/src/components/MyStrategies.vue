<template>
  <el-card class="strategy-card">
    <template #header>
      <div class="card-header">
        <span>我的量化策略 (实盘运行)</span>
        <el-button type="primary" size="small" @click="openDialog()">新建实盘策略</el-button>
      </div>
    </template>

    <el-table :data="strategies" v-loading="loading" style="width: 100%" border stripe>
      <el-table-column prop="name" label="策略名称" width="200" align="center" />

      <el-table-column label="交易股票池" align="center" show-overflow-tooltip>
        <template #default="scope">
          {{ formatStockPool(scope.row.stock_pool) }}
        </template>
      </el-table-column>

      <el-table-column label="多因子参数" width="220" align="center">
        <template #default="scope">
          <div style="font-size: 12px; line-height: 1.5; text-align: left; display: inline-block;">
            动量权重: {{ parseConfig(scope.row.code).weight_mom }}<br/>
            偏离权重: {{ parseConfig(scope.row.code).weight_bias }}<br/>
            选股Top: {{ parseConfig(scope.row.code).top_n }}
          </div>
        </template>
      </el-table-column>

      <el-table-column label="运行状态" width="120" align="center">
        <template #default="scope">
          <el-switch
            v-model="scope.row.status"
            active-value="active"
            inactive-value="stopped"
            active-text="运行"
            inactive-text="停止"
            @change="toggleStatus(scope.row)"
          />
        </template>
      </el-table-column>

      <el-table-column label="操作" width="150" align="center">
        <template #default="scope">
          <el-button size="small" @click="openDialog(scope.row)">参数设置</el-button>
          <el-popconfirm title="确定删除这个策略吗？" @confirm="deleteStrategy(scope.row.id)">
            <template #reference>
              <el-button size="small" type="danger" style="margin-left: 5px;">删除</el-button>
            </template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog
      v-model="dialogVisible"
      :title="currentStrategy.id ? '调整多因子参数' : '新建多因子策略'"
      width="600px"
      destroy-on-close
    >
      <el-form label-width="120px" :model="currentStrategy">
        <el-form-item label="策略名称">
          <el-input v-model="currentStrategy.name" placeholder="例如: 动量轮动实盘策略" />
        </el-form-item>

        <el-form-item label="股票池">
          <div class="stock-pool-wrapper">
            <el-checkbox
              v-model="currentStrategy.use_all_stocks"
              @change="handleAllStocksChange"
            >
              使用全部股票
            </el-checkbox>

            <el-input
              v-model="currentStrategy.stock_pool"
              type="textarea"
              :rows="3"
              :disabled="currentStrategy.use_all_stocks"
              :placeholder="currentStrategy.use_all_stocks
                ? '已选择全部股票，保存后后端会自动展开股票池'
                : '英文逗号分隔，例如: sz.300394, sh.600000'"
              style="margin-top: 8px;"
            />

            <div class="stock-pool-tip">
              <template v-if="currentStrategy.use_all_stocks">
                当前策略将使用全市场股票池。
              </template>
              <template v-else>
                手动输入时请使用英文逗号分隔股票代码。
              </template>
            </div>
          </div>
        </el-form-item>

        <el-divider>多因子权重配置 (矩阵 Z-Score)</el-divider>

        <el-form-item label="动量因子权重">
          <el-slider v-model="currentStrategy.weight_mom" :min="-1" :max="1" :step="0.1" show-input />
        </el-form-item>

        <el-form-item label="均线偏离权重">
          <el-slider v-model="currentStrategy.weight_bias" :min="-1" :max="1" :step="0.1" show-input />
        </el-form-item>

        <el-form-item label="每日选股数 (Top N)">
          <el-input-number v-model="currentStrategy.top_n" :min="1" :max="20" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveStrategy" :loading="saving">保存并应用</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'

const ALL_STOCK_SENTINEL = '__ALL__'
const ALL_STOCK_LABEL = '全部股票'

const strategies = ref([])
const loading = ref(false)
const saving = ref(false)
const dialogVisible = ref(false)

const createDefaultStrategy = () => ({
  id: null,
  name: '新建多因子策略',
  stock_pool: '',
  use_all_stocks: false,
  weight_mom: 0.5,
  weight_bias: -0.5,
  top_n: 2
})

const currentStrategy = ref(createDefaultStrategy())

const getApi = () => {
  return axios.create({
    baseURL: 'http://127.0.0.1:8000/',
    headers: { Authorization: 'Token ' + localStorage.getItem('token') }
  })
}

const parseConfig = (codeStr) => {
  try {
    return JSON.parse(codeStr)
  } catch (e) {
    return { weight_mom: 0, weight_bias: 0, top_n: 0 }
  }
}

const isAllStockPool = (value = '') => {
  const raw = String(value).trim()
  const upper = raw.toUpperCase()
  return ['__ALL__', 'ALL', 'ALL_STOCKS'].includes(upper) || ['全部', '全部股票'].includes(raw)
}

const normalizeStockPool = (value = '') => {
  const raw = String(value).trim()
  if (!raw) return ''
  if (isAllStockPool(raw)) return ALL_STOCK_SENTINEL

  return raw
    .replace(/，/g, ',')
    .replace(/\n/g, ',')
    .split(',')
    .map(item => item.trim())
    .filter(Boolean)
    .filter((item, index, arr) => arr.indexOf(item) === index)
    .join(',')
}

const formatStockPool = (value = '') => {
  if (!value) return '-'
  if (isAllStockPool(value)) return ALL_STOCK_LABEL
  return normalizeStockPool(value)
}

// 获取策略列表
const fetchStrategies = async () => {
  loading.value = true
  try {
    const res = await getApi().get('api/trade/strategy/')
    if (res.data.code === 200) {
      strategies.value = res.data.data
    }
  } catch (e) {
    console.error('获取策略失败', e)
  } finally {
    loading.value = false
  }
}

// 切换策略状态
const toggleStatus = async (row) => {
  try {
    const res = await getApi().post('api/trade/strategy/', {
      id: row.id,
      status: row.status
    })
    if (res.data.code === 200) {
      ElMessage.success(row.status === 'active' ? '引擎已就绪！将在开/尾盘执行轮动' : '策略已停止')
    } else {
      throw new Error(res.data.msg)
    }
  } catch (e) {
    ElMessage.error('状态切换失败')
    row.status = row.status === 'active' ? 'stopped' : 'active'
  }
}

const handleAllStocksChange = (checked) => {
  if (checked) {
    currentStrategy.value.stock_pool = ''
  }
}

// 打开弹窗并解析 JSON
const openDialog = (row = null) => {
  if (row) {
    const config = parseConfig(row.code)
    const normalizedPool = normalizeStockPool(row.stock_pool)
    const useAllStocks = isAllStockPool(normalizedPool)

    currentStrategy.value = {
      id: row.id,
      name: row.name,
      stock_pool: useAllStocks ? '' : normalizedPool,
      use_all_stocks: useAllStocks,
      weight_mom: config.weight_mom ?? 0.5,
      weight_bias: config.weight_bias ?? -0.5,
      top_n: config.top_n ?? 2
    }
  } else {
    currentStrategy.value = createDefaultStrategy()
  }

  dialogVisible.value = true
}

// 保存策略
const saveStrategy = async () => {
  const name = String(currentStrategy.value.name || '').trim()
  if (!name) {
    ElMessage.warning('请填写策略名称')
    return
  }

  const finalStockPool = currentStrategy.value.use_all_stocks
    ? ALL_STOCK_SENTINEL
    : normalizeStockPool(currentStrategy.value.stock_pool)

  if (!finalStockPool) {
    ElMessage.warning('请填写股票池，或勾选“使用全部股票”')
    return
  }

  saving.value = true

  const payload = {
    name,
    stock_pool: finalStockPool,
    code: JSON.stringify({
      weight_mom: currentStrategy.value.weight_mom,
      weight_bias: currentStrategy.value.weight_bias,
      top_n: currentStrategy.value.top_n
    })
  }

  if (currentStrategy.value.id) {
    payload.id = currentStrategy.value.id
  }

  try {
    const res = await getApi().post('api/trade/strategy/', payload)
    if (res.data.code === 200) {
      ElMessage.success('保存成功')
      dialogVisible.value = false
      fetchStrategies()
    } else {
      ElMessage.error(res.data.msg || '保存失败')
    }
  } catch (e) {
    ElMessage.error('保存请求失败')
  } finally {
    saving.value = false
  }
}

// 删除策略
const deleteStrategy = async (id) => {
  try {
    const res = await getApi().delete('api/trade/strategy/', { data: { id } })
    if (res.data.code === 200) {
      ElMessage.success('删除成功')
      fetchStrategies()
    }
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

onMounted(() => {
  fetchStrategies()
})
</script>

<style scoped>
.strategy-card {
  margin-top: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.stock-pool-wrapper {
  width: 100%;
}

.stock-pool-tip {
  margin-top: 8px;
  font-size: 12px;
  color: #909399;
  line-height: 1.5;
}
</style>