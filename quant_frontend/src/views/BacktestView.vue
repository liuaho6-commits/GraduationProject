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
              <el-input v-model="form.task_name" disabled placeholder="请输入任务名称" />
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
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, watch, nextTick, onBeforeUnmount } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { VideoPlay } from '@element-plus/icons-vue'
import * as echarts from 'echarts'

// 1. 定义默认配置
const defaultForm = {
  task_name: '动量反转混合策略',
  initial_capital: 100000,
  weight_mom: 0.6,
  weight_bias: -0.4,
  top_n: 2
}
const defaultDateRange = ['2024-01-01', '2025-12-31']

// 2. 尝试从 localStorage 读取历史配置
const savedForm = JSON.parse(localStorage.getItem('quant_backtest_form'))
const savedDateRange = JSON.parse(localStorage.getItem('quant_backtest_dateRange'))

// 3. 初始化响应式数据（如果有历史记录则合并，并强制覆盖不可修改的 task_name）
const form = reactive({
  ...defaultForm,
  ...(savedForm || {}),
  task_name: defaultForm.task_name // 确保任务名一直是默认的
})
const dateRange = ref(savedDateRange || defaultDateRange)

// 4. 使用 watch 深度监听数据变化，实时保存到 localStorage
watch(form, (newVal) => {
  localStorage.setItem('quant_backtest_form', JSON.stringify(newVal))
}, { deep: true })

watch(dateRange, (newVal) => {
  localStorage.setItem('quant_backtest_dateRange', JSON.stringify(newVal))
})

// 5. 恢复默认配置的方法
const resetForm = () => {
  Object.assign(form, defaultForm)
  dateRange.value = [...defaultDateRange]
  ElMessage.success('已恢复默认配置')
}

// 以下为回测与图表渲染逻辑 (保持不变)
const loading = ref(false)
const resultData = ref(null)
const chartRef = ref(null)
let myChart = null

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
        renderChart(resultData.value.equity_curve)
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

const renderChart = (curveData) => {
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
        const dailyReturn = item ? (item.daily_return * 100).toFixed(2) + '%' : '--';
        return `${date}<br/>资金净值: ${equity}<br/>单日收益: ${dailyReturn}`;
      }
    },
    toolbox: {
      feature: {
        dataView: {
          show: true,
          readOnly: true,
          title: '数据视图',
          lang: ['数据视图', '关闭', '刷新']
        },
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