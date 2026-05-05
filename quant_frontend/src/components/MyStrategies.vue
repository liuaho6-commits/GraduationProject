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
            调仓: 每日 Top {{ parseConfig(scope.row.code).top_n }}<br/>
            启用因子: {{ enabledFactorCount(parseConfig(scope.row.code).factors) }} 个
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

        <el-divider>每日选股策略控制</el-divider>

        <el-form-item label="策略模板">
          <el-select v-model="currentStrategy.preset_code" style="width: 100%" @change="applyStrategyPreset">
            <el-option
              v-for="preset in STRATEGY_PRESETS"
              :key="preset.code"
              :label="preset.name"
              :value="preset.code"
            />
          </el-select>
        </el-form-item>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="目标持仓数">
              <el-input-number v-model="currentStrategy.top_n" :min="1" :max="20" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="允许空仓">
              <el-switch v-model="currentStrategy.allow_cash" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="买入阈值">
              <el-input-number v-model="currentStrategy.buy_threshold" :min="-5" :max="5" :step="0.1" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="手续费">
          <div class="fee-text">万一免五：成交额 0.01%，最低 0 元</div>
        </el-form-item>

        <el-divider>内置因子权重</el-divider>

        <el-table :data="currentStrategy.factors" border size="small">
          <el-table-column label="启用" width="70" align="center">
            <template #default="scope">
              <el-switch v-model="scope.row.enabled" />
            </template>
          </el-table-column>
          <el-table-column label="因子" width="150">
            <template #default="scope">
              <div class="factor-name">{{ getFactorMeta(scope.row.code).name }}</div>
              <div class="factor-code">{{ scope.row.code }}</div>
            </template>
          </el-table-column>
          <el-table-column label="权重" width="150" align="center">
            <template #default="scope">
              <el-input-number
                v-model="scope.row.weight"
                :min="-1"
                :max="1"
                :step="0.1"
                size="small"
                controls-position="right"
              />
            </template>
          </el-table-column>
        </el-table>
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

const BUILTIN_FACTORS = [
  { code: 'mom_20', name: '20日动量', description: '近20个交易日收益率，偏中期趋势', weight: 0.45, enabled: true },
  { code: 'rev_5', name: '5日反转', description: '近5个交易日收益率取反，短期回调加分', weight: 0.1, enabled: true },
  { code: 'vol_20', name: '20日低波动', description: '近20个交易日收益波动率取反，波动越小越好', weight: 0.2, enabled: true },
  { code: 'trend_20', name: '20日均线趋势', description: '收盘价相对20日均线的偏离，强于均线加分', weight: 0.25, enabled: true }
]

const factorMetaMap = Object.fromEntries(BUILTIN_FACTORS.map(item => [item.code, item]))
const createDefaultFactors = () => BUILTIN_FACTORS.map(item => ({
  code: item.code,
  weight: item.weight,
  enabled: item.enabled
}))

const STRATEGY_PRESETS = [
  {
    code: 'balanced',
    name: '均衡默认组合',
    config: {
      top_n: 5,
      buy_threshold: 0.3,
      allow_cash: true,
      factors: [
        { code: 'mom_20', weight: 0.45, enabled: true },
        { code: 'rev_5', weight: 0.1, enabled: true },
        { code: 'vol_20', weight: 0.2, enabled: true },
        { code: 'trend_20', weight: 0.25, enabled: true }
      ]
    }
  },
  {
    code: 'aggressive',
    name: '高收益进攻组合',
    config: {
      top_n: 3,
      buy_threshold: 0.1,
      allow_cash: true,
      factors: [
        { code: 'mom_20', weight: 0.6, enabled: true },
        { code: 'rev_5', weight: 0.05, enabled: true },
        { code: 'vol_20', weight: 0.05, enabled: true },
        { code: 'trend_20', weight: 0.3, enabled: true }
      ]
    }
  },
  {
    code: 'low_drawdown',
    name: '低回撤防守组合',
    config: {
      top_n: 8,
      buy_threshold: 0.5,
      allow_cash: true,
      factors: [
        { code: 'mom_20', weight: 0.2, enabled: true },
        { code: 'rev_5', weight: 0.1, enabled: true },
        { code: 'vol_20', weight: 0.5, enabled: true },
        { code: 'trend_20', weight: 0.2, enabled: true }
      ]
    }
  },
  {
    code: 'low_turnover',
    name: '稳健分散组合',
    config: {
      top_n: 6,
      buy_threshold: 0.25,
      allow_cash: true,
      factors: [
        { code: 'mom_20', weight: 0.4, enabled: true },
        { code: 'rev_5', weight: 0.05, enabled: true },
        { code: 'vol_20', weight: 0.25, enabled: true },
        { code: 'trend_20', weight: 0.3, enabled: true }
      ]
    }
  },
  {
    code: 'trend',
    name: '中期趋势组合',
    config: {
      top_n: 5,
      buy_threshold: 0.2,
      allow_cash: true,
      factors: [
        { code: 'mom_20', weight: 0.6, enabled: true },
        { code: 'rev_5', weight: 0, enabled: false },
        { code: 'vol_20', weight: 0.1, enabled: true },
        { code: 'trend_20', weight: 0.3, enabled: true }
      ]
    }
  },
  {
    code: 'pullback',
    name: '短期回调修复组合',
    config: {
      top_n: 5,
      buy_threshold: 0.1,
      allow_cash: true,
      factors: [
        { code: 'mom_20', weight: 0.3, enabled: true },
        { code: 'rev_5', weight: 0.4, enabled: true },
        { code: 'vol_20', weight: 0.1, enabled: true },
        { code: 'trend_20', weight: 0.2, enabled: true }
      ]
    }
  },
  {
    code: 'strict_cash',
    name: '空仓择时严格组合',
    config: {
      top_n: 5,
      buy_threshold: 0.8,
      allow_cash: true,
      factors: [
        { code: 'mom_20', weight: 0.45, enabled: true },
        { code: 'rev_5', weight: 0.05, enabled: true },
        { code: 'vol_20', weight: 0.25, enabled: true },
        { code: 'trend_20', weight: 0.25, enabled: true }
      ]
    }
  }
]

const normalizeFactors = (factors = []) => {
  const savedMap = Object.fromEntries((factors || []).map(item => [item.code, item]))
  return BUILTIN_FACTORS.map(item => ({
    code: item.code,
    weight: Number(savedMap[item.code]?.weight ?? item.weight),
    enabled: Boolean(savedMap[item.code]?.enabled ?? item.enabled)
  }))
}

const strategies = ref([])
const loading = ref(false)
const saving = ref(false)
const dialogVisible = ref(false)

const createDefaultStrategy = () => ({
  id: null,
  preset_code: 'balanced',
  name: '新建多因子策略',
  stock_pool: '',
  use_all_stocks: false,
  top_n: 5,
  buy_threshold: 0.3,
  allow_cash: true,
  fee_rate: 0.0001,
  min_fee: 0,
  factors: createDefaultFactors()
})

const currentStrategy = ref(createDefaultStrategy())

const getApi = () => {
  return axios.create({
    baseURL: 'http://127.0.0.1:8000/',
    headers: { Authorization: 'Token ' + localStorage.getItem('token') }
  })
}

const normalizeConfig = (config = {}) => ({
  preset_code: config.preset_code || 'balanced',
  top_n: Number(config.top_n ?? 5),
  buy_threshold: Number(config.buy_threshold ?? 0.3),
  allow_cash: config.allow_cash ?? true,
  fee_rate: 0.0001,
  min_fee: 0,
  factors: normalizeFactors(config.factors)
})

const parseConfig = (codeStr) => {
  try {
    return normalizeConfig(JSON.parse(codeStr))
  } catch (e) {
    return normalizeConfig()
  }
}

const getFactorMeta = (code) => factorMetaMap[code] || { name: code, description: '' }
const enabledFactorCount = (factors = []) => factors.filter(item => item.enabled && Number(item.weight) !== 0).length

const buildStrategyConfig = () => ({
  preset_code: currentStrategy.value.preset_code,
  top_n: currentStrategy.value.top_n,
  buy_threshold: currentStrategy.value.buy_threshold,
  allow_cash: currentStrategy.value.allow_cash,
  fee_rate: 0.0001,
  min_fee: 0,
  factors: currentStrategy.value.factors.map(item => ({
    code: item.code,
    weight: Number(item.weight),
    enabled: Boolean(item.enabled)
  }))
})

const applyConfigToCurrentStrategy = (config) => {
  currentStrategy.value.top_n = config.top_n
  currentStrategy.value.buy_threshold = config.buy_threshold
  currentStrategy.value.allow_cash = config.allow_cash
  currentStrategy.value.fee_rate = 0.0001
  currentStrategy.value.min_fee = 0
  currentStrategy.value.factors = normalizeFactors(config.factors)
}

const applyStrategyPreset = (presetCode) => {
  const preset = STRATEGY_PRESETS.find(item => item.code === presetCode)
  if (!preset) return
  currentStrategy.value.preset_code = presetCode
  applyConfigToCurrentStrategy(preset.config)
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
      preset_code: config.preset_code,
      stock_pool: useAllStocks ? '' : normalizedPool,
      use_all_stocks: useAllStocks,
      top_n: config.top_n,
      buy_threshold: config.buy_threshold,
      allow_cash: config.allow_cash,
      fee_rate: config.fee_rate,
      min_fee: config.min_fee,
      factors: normalizeFactors(config.factors)
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
    code: JSON.stringify(buildStrategyConfig())
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

.factor-name {
  font-weight: 600;
  color: #303133;
}

.factor-code {
  margin-top: 2px;
  font-size: 12px;
  color: #909399;
  font-family: 'Roboto Mono', monospace;
}

.fee-text {
  color: #606266;
  font-size: 13px;
  line-height: 32px;
}
</style>
