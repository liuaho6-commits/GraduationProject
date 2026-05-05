<template>
  <div class="backtest-container">
    <h2>多因子量化回测引擎 (Spark 分布式)</h2>

    <el-card class="config-card">
      <template #header>
        <div class="card-header">
          <span>回测参数配置</span>
        </div>
      </template>
      <el-form :model="form" label-width="120px" class="demo-form-inline">
        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="任务名称">
              <el-input v-model="form.task_name" placeholder="请输入任务名称" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="起止日期">
              <el-date-picker
                v-model="dateRange"
                type="daterange"
                range-separator="至"
                start-placeholder="开始日期"
                end-placeholder="结束日期"
                value-format="YYYY-MM-DD"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="初始资金">
              <el-input-number v-model="form.initial_capital" :min="10000" :step="10000" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-divider>每日选股策略控制</el-divider>

        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="策略模板">
              <el-select v-model="selectedPreset" style="width: 100%" @change="applyPreset">
                <el-option
                  v-for="preset in STRATEGY_PRESETS"
                  :key="preset.code"
                  :label="preset.name"
                  :value="preset.code"
                />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="目标持仓数">
              <el-input-number v-model="form.top_n" :min="1" :max="20" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="允许空仓">
              <el-switch v-model="form.allow_cash" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="买入分数阈值">
              <el-input-number v-model="form.buy_threshold" :min="-5" :max="5" :step="0.1" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="手续费">
              <div class="fee-text">万一免五：成交额 0.01%，最低 0 元</div>
            </el-form-item>
          </el-col>
        </el-row>

        <el-divider>内置因子权重</el-divider>

        <el-table :data="form.factors" border size="small" class="factor-table">
          <el-table-column label="启用" width="80" align="center">
            <template #default="scope">
              <el-switch v-model="scope.row.enabled" />
            </template>
          </el-table-column>
          <el-table-column label="因子" width="180">
            <template #default="scope">
              <div class="factor-name">{{ getFactorMeta(scope.row.code).name }}</div>
              <div class="factor-code">{{ scope.row.code }}</div>
            </template>
          </el-table-column>
          <el-table-column label="说明">
            <template #default="scope">
              <span class="factor-desc">{{ getFactorMeta(scope.row.code).description }}</span>
            </template>
          </el-table-column>
          <el-table-column label="权重" width="180" align="center">
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

        <div style="text-align: center; margin-top: 20px;">
          <el-button type="primary" size="large" :loading="loading" @click="runBacktest" style="width: 200px;">
            <el-icon style="margin-right: 8px;"><VideoPlay /></el-icon> 开始执行分布式回测
          </el-button>
          <el-button size="large" @click="resetForm" style="margin-left: 15px;">恢复默认</el-button>
        </div>
      </el-form>
    </el-card>

    <el-card class="result-card" v-if="resultData" v-loading="loading">
      <template #header>
        <div class="card-header">
          <span>回测结果 (任务ID: {{ resultData.task_id }})</span>
        </div>
      </template>

      <el-row :gutter="20" class="indicators">
        <el-col :span="6">
          <div class="indicator-item">
            <div class="label">累计总收益率</div>
            <div class="value" :class="resultData.total_return >= 0 ? 'up' : 'down'">
              {{ (resultData.total_return * 100).toFixed(2) }}%
            </div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="indicator-item">
            <div class="label">年化收益率</div>
            <div class="value" :class="resultData.annualized_return >= 0 ? 'up' : 'down'">
              {{ (resultData.annualized_return * 100).toFixed(2) }}%
            </div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="indicator-item">
            <div class="label">期末总资产</div>
            <div class="value">{{ resultData.final_capital.toFixed(2) }}</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="indicator-item">
            <div class="label">平均换手率</div>
            <div class="value">{{ ((resultData.avg_turnover || 0) * 100).toFixed(2) }}%</div>
          </div>
        </el-col>
      </el-row>

      <div class="result-note">
        回测天数 {{ resultData.equity_curve.length }} 天，空仓天数 {{ resultData.cash_days || 0 }} 天，累计换手 {{ ((resultData.total_turnover || 0) * 100).toFixed(2) }}%
      </div>

      <div ref="chartRef" class="chart-container"></div>

      <div style="text-align: center; margin-top: 20px; margin-bottom: 20px;">
        <el-button type="success" size="large" @click="deployToRealTrade">
          <el-icon style="margin-right: 8px;"><Position /></el-icon>
          一键部署为实盘多因子策略
        </el-button>
      </div>

      <el-divider>交易与持仓明细 (可点击表头按日期排序)</el-divider>

      <el-table
        :data="resultData.trade_records"
        height="400"
        border
        stripe
        style="width: 100%; margin-top: 20px;"
        :default-sort="{ prop: 'date', order: 'descending' }"
      >
        <el-table-column prop="date" label="交易日期" width="150" align="center" sortable />
        <el-table-column prop="stocks" label="当日持仓标的" align="center">
          <template #default="scope">
            <el-tag
              v-if="scope.row.stocks === '空仓避险'"
              type="danger"
              size="small"
            >
              空仓避险
            </el-tag>
            <el-tag
              v-else
              v-for="stock in scope.row.stocks.split(', ')"
              :key="stock"
              size="small"
              style="margin-right: 5px;"
            >
              {{ stock }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="daily_return" label="单日收益率" width="150" align="center">
          <template #default="scope">
            <span :class="scope.row.daily_return > 0 ? 'up' : (scope.row.daily_return < 0 ? 'down' : '')" style="font-weight: bold;">
              {{ (scope.row.daily_return * 100).toFixed(2) }}%
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="equity" label="收盘总资金 (元)" width="180" align="center" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, watch, nextTick, onBeforeUnmount } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { VideoPlay, Position } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import { useRouter } from 'vue-router'

const router = useRouter()

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

const createDefaultForm = () => ({
  preset_code: 'balanced',
  task_name: '每日多因子轮动策略',
  initial_capital: 100000,
  top_n: 5,
  buy_threshold: 0.3,
  allow_cash: true,
  fee_rate: 0.0001,
  min_fee: 0,
  factors: createDefaultFactors()
})

const defaultDateRange = ['2024-01-01', '2025-12-31']

const savedForm = JSON.parse(localStorage.getItem('quant_backtest_form'))
const savedDateRange = JSON.parse(localStorage.getItem('quant_backtest_dateRange'))
const defaultForm = createDefaultForm()

const form = reactive({
  ...defaultForm,
  ...(savedForm || {}),
  task_name: defaultForm.task_name,
  factors: normalizeFactors(savedForm?.factors || defaultForm.factors)
})
const dateRange = ref(savedDateRange || defaultDateRange)
const selectedPreset = ref(savedForm?.preset_code || 'balanced')

const getFactorMeta = (code) => factorMetaMap[code] || { name: code, description: '' }

const applyConfigToForm = (config) => {
  form.top_n = config.top_n
  form.buy_threshold = config.buy_threshold
  form.allow_cash = config.allow_cash
  form.fee_rate = 0.0001
  form.min_fee = 0
  form.factors = normalizeFactors(config.factors)
}

const applyPreset = (presetCode) => {
  const preset = STRATEGY_PRESETS.find(item => item.code === presetCode)
  if (!preset) return
  form.preset_code = presetCode
  applyConfigToForm(preset.config)
}

const buildStrategyConfig = () => ({
  preset_code: selectedPreset.value,
  top_n: form.top_n,
  buy_threshold: form.buy_threshold,
  allow_cash: form.allow_cash,
  fee_rate: 0.0001,
  min_fee: 0,
  factors: form.factors.map(item => ({
    code: item.code,
    weight: Number(item.weight),
    enabled: Boolean(item.enabled)
  }))
})

watch(form, (newVal) => {
  localStorage.setItem('quant_backtest_form', JSON.stringify(newVal))
}, { deep: true })

watch(dateRange, (newVal) => {
  localStorage.setItem('quant_backtest_dateRange', JSON.stringify(newVal))
})

const resetForm = () => {
  Object.assign(form, createDefaultForm())
  selectedPreset.value = 'balanced'
  applyPreset(selectedPreset.value)
  dateRange.value = [...defaultDateRange]
  ElMessage.success('已恢复默认配置')
}

const loading = ref(false)
const resultData = ref(null)
const chartRef = ref(null)
let myChart = null

// 🟢 这里删除了之前那个产生错觉的 reversedTradeRecords computed 属性

const runBacktest = async () => {
  if (!dateRange.value || dateRange.value.length !== 2) {
    ElMessage.warning('请选择起止日期')
    return
  }
  loading.value = true
  resultData.value = null

  try {
    const payload = {
      task_name: form.task_name,
      start_date: dateRange.value[0],
      end_date: dateRange.value[1],
      initial_capital: form.initial_capital,
      ...buildStrategyConfig()
    }

    const response = await axios.post('http://127.0.0.1:8000/api/backtest/run/', payload)

    if (response.data.code === 200) {
      ElMessage.success('分布式集群回测计算完成！')
      resultData.value = response.data.data
      nextTick(() => {
        renderChart(resultData.value.equity_curve, form.initial_capital)
      })
    } else {
      ElMessage.error(response.data.message || '回测失败')
    }
  } catch (error) {
    console.error(error)
    ElMessage.error('网络请求异常，请检查后端运行状态')
  } finally {
    loading.value = false
  }
}

// 一键部署为实盘策略方法
const deployToRealTrade = async () => {
  try {
    const api = axios.create({
      baseURL: 'http://127.0.0.1:8000/',
      headers: { 'Authorization': 'Token ' + localStorage.getItem('token') }
    })

    // 把每日多因子配置打包成 JSON 字符串
    const strategyConfig = JSON.stringify(buildStrategyConfig())

    const payload = {
      name: form.task_name + ' (实盘)',
      stock_pool: 'sz.300394', // 默认填入一个测试股票，可以在面板中修改
      code: strategyConfig,
      status: 'active' // 部署后直接激活
    }

    const res = await api.post('api/trade/strategy/', payload)

    if (res.data.code === 200) {
      ElMessage.success('实盘部署成功！策略引擎将在开/尾盘时自动执行因子选股。')
      // 部署成功后，自动跳转回 Dashboard 查看
      setTimeout(() => {
        router.push('/dashboard')
      }, 1500)
    } else {
      ElMessage.error(res.data.msg || '部署失败')
    }
  } catch (error) {
    ElMessage.error('网络错误，部署失败')
  }
}

const renderChart = (curveData, baseCapital) => {
  if (!chartRef.value) return
  if (myChart) myChart.dispose()
  myChart = echarts.init(chartRef.value)

  const dates = curveData.map(item => item.date)
  const equities = curveData.map(item => item.equity)

  const option = {
    title: { text: '资金净值曲线', left: 'center' },
    tooltip: {
      trigger: 'axis',
      formatter: function (params) {
        const date = params[0].axisValue;
        const equity = params[0].data;
        const item = curveData.find(d => d.date === date);

        let dailyReturnStr = '--';
        let cumReturnStr = '--';

        if (item) {
          const dailyReturn = (item.daily_return * 100).toFixed(2);
          const dailyColor = item.daily_return >= 0 ? '#f56c6c' : '#67c23a';
          dailyReturnStr = `<span style="color: ${dailyColor}; font-weight: bold;">${dailyReturn}%</span>`;

          const cumReturn = (((equity - baseCapital) / baseCapital) * 100).toFixed(2);
          const cumColor = (equity - baseCapital) >= 0 ? '#f56c6c' : '#67c23a';
          cumReturnStr = `<span style="color: ${cumColor}; font-weight: bold;">${cumReturn}%</span>`;
        }

        return `
          <div style="font-size: 14px; line-height: 24px;">
            <b>${date}</b><br/>
            资金净值: ${equity.toFixed(2)}<br/>
            单日收益: ${dailyReturnStr}<br/>
            累计收益: ${cumReturnStr}
          </div>
        `;
      }
    },
    toolbox: {
      feature: {
        dataView: { show: true, readOnly: true, title: '数据视图', lang: ['数据视图', '关闭', '刷新'] },
        restore: { show: true, title: '还原' },
        saveAsImage: { show: true, title: '下载图表' }
      }
    },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: { type: 'category', boundaryGap: false, data: dates },
    yAxis: { type: 'value', scale: true },
    series: [
      {
        name: '总资金', type: 'line', data: equities, smooth: true,
        itemStyle: { color: '#409EFF' },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(64,158,255,0.5)' },
            { offset: 1, color: 'rgba(64,158,255,0.1)' }
          ])
        }
      }
    ]
  }
  myChart.setOption(option)
}

window.addEventListener('resize', () => { if (myChart) myChart.resize() })
onBeforeUnmount(() => { if (myChart) myChart.dispose() })
</script>

<style scoped>
.backtest-container { padding: 20px; }
.config-card { margin-bottom: 20px; }
.factor-desc { font-size: 12px; color: #909399; margin-top: 4px; line-height: 1.2; }
.factor-table { margin-top: 8px; }
.factor-name { font-weight: 600; color: #303133; }
.factor-code { margin-top: 2px; font-size: 12px; color: #909399; font-family: 'Roboto Mono', monospace; }
.fee-text { color: #606266; font-size: 13px; line-height: 32px; }
.result-card { margin-top: 20px; }
.indicators { margin-bottom: 30px; text-align: center; }
.indicator-item { padding: 15px; background-color: #f8f9fa; border-radius: 8px; }
.indicator-item .label { font-size: 14px; color: #606266; margin-bottom: 8px; }
.indicator-item .value { font-size: 24px; font-weight: bold; }
.result-note { margin: -12px 0 24px; text-align: center; color: #606266; font-size: 13px; }
.up { color: #f56c6c; }
.down { color: #67c23a; }
.chart-container { width: 100%; height: 400px; }
</style>
