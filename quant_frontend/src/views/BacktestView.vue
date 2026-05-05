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
                unlink-panels
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

        <el-divider>多因子权重与截面配置</el-divider>

        <el-row :gutter="40">
          <el-col :span="8">
            <el-form-item label="动量因子权重">
              <el-slider v-model="form.weight_mom" :min="-1" :max="1" :step="0.1" show-input />
              <div class="factor-desc">正值代表追涨，负值代表抄底</div>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="均线偏离权重">
              <el-slider v-model="form.weight_bias" :min="-1" :max="1" :step="0.1" show-input />
              <div class="factor-desc">负值代表均线反转策略</div>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="每日选股数 (Top N)">
              <el-input-number v-model="form.top_n" :min="1" :max="10" />
            </el-form-item>
          </el-col>
        </el-row>

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
            <div class="label">回测天数</div>
            <div class="value">{{ resultData.equity_curve.length }} 天</div>
          </div>
        </el-col>
      </el-row>

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

const defaultForm = {
  task_name: '动量反转混合策略',
  initial_capital: 100000,
  weight_mom: 0.6,
  weight_bias: -0.4,
  top_n: 2
}
const defaultDateRange = ['2024-01-01', '2025-12-31']

const savedForm = JSON.parse(localStorage.getItem('quant_backtest_form'))
const savedDateRange = JSON.parse(localStorage.getItem('quant_backtest_dateRange'))

const form = reactive({
  ...defaultForm,
  ...(savedForm || {}),
  task_name: defaultForm.task_name
})
const dateRange = ref(savedDateRange || defaultDateRange)

watch(form, (newVal) => {
  localStorage.setItem('quant_backtest_form', JSON.stringify(newVal))
}, { deep: true })

watch(dateRange, (newVal) => {
  localStorage.setItem('quant_backtest_dateRange', JSON.stringify(newVal))
})

const resetForm = () => {
  Object.assign(form, defaultForm)
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
      weight_mom: form.weight_mom,
      weight_bias: form.weight_bias,
      top_n: form.top_n
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

    // 把多因子权重配置打包成 JSON 字符串
    const strategyConfig = JSON.stringify({
      weight_mom: form.weight_mom,
      weight_bias: form.weight_bias,
      top_n: form.top_n
    })

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
.result-card { margin-top: 20px; }
.indicators { margin-bottom: 30px; text-align: center; }
.indicator-item { padding: 15px; background-color: #f8f9fa; border-radius: 8px; }
.indicator-item .label { font-size: 14px; color: #606266; margin-bottom: 8px; }
.indicator-item .value { font-size: 24px; font-weight: bold; }
.up { color: #f56c6c; }
.down { color: #67c23a; }
.chart-container { width: 100%; height: 400px; }
</style>
