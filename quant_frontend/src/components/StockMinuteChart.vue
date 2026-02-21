<template>
  <div class="chart-wrapper">
    <div ref="chartContainer" class="echart-box"></div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  data: { type: Array, default: () => [] }
})

const chartContainer = ref(null)
let myChart = null

const color = {
  up: '#F56C6C',
  down: '#00C853',
  volUp: '#F56C6C',
  volDown: '#00C853'
}

const render = () => {
  if (!chartContainer.value) return

  if (!myChart) {
    myChart = echarts.init(chartContainer.value)
    window.addEventListener('resize', () => myChart && myChart.resize())
  }

  const rawData = props.data || []

  // 1. 无数据处理
  if (rawData.length === 0) {
    myChart.setOption({
      title: { text: '暂无数据', left: 'center', top: 'center', textStyle: { color: '#ccc' } },
      grid: [], xAxis: [], yAxis: [], series: []
    }, true)
    return
  }

  const categoryData = []
  const kData = []
  const volData = []

  rawData.forEach(item => {
    let dateStr = item.date
    if (dateStr && dateStr.length > 10) {
      dateStr = dateStr.substring(5, 16)
    }
    categoryData.push(dateStr)
    kData.push([item.open, item.close, item.low, item.high])
    volData.push({
      value: item.volume,
      itemStyle: {
        color: item.close >= item.open ? color.volUp : color.volDown
      }
    })
  })

  // 2. 智能缩放计算
  const currentOpt = myChart.getOption()
  const totalLen = categoryData.length
  const DEFAULT_WINDOW_SIZE = 60
  let finalStartValue = 0
  let finalEndValue = totalLen - 1
  let shouldSnapToEnd = true
  let currentWindowSize = DEFAULT_WINDOW_SIZE

  // 检查用户是否正在查看历史数据
  if (currentOpt && currentOpt.dataZoom && currentOpt.dataZoom.length > 0) {
    const zoomState = currentOpt.dataZoom[0]
    if (zoomState.end != null && zoomState.end < 98) {
      shouldSnapToEnd = false
    }
    const sVal = zoomState.startValue
    const eVal = zoomState.endValue
    if (typeof sVal === 'number' && typeof eVal === 'number') {
      currentWindowSize = eVal - sVal
      if (currentWindowSize < 5) currentWindowSize = 5
    }
  }

  if (shouldSnapToEnd) {
    finalEndValue = totalLen - 1
    finalStartValue = Math.max(0, finalEndValue - currentWindowSize)
  } else if (currentOpt && currentOpt.dataZoom && currentOpt.dataZoom[0]) {
    finalStartValue = currentOpt.dataZoom[0].startValue
    finalEndValue = currentOpt.dataZoom[0].endValue
  }

  // 3. 构建 Option
  const option = {
    title: { text: '' }, // 🟢 显式清空标题
    animation: false,
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      backgroundColor: 'rgba(255, 255, 255, 0.95)',
      formatter: (params) => {
        const kParam = params.find(p => p.seriesName === 'K线')
        if (!kParam) return ''
        const i = kParam.dataIndex
        const item = rawData[i]
        let chgStr = '0.00%'
        if (i > 0) {
          const chg = (item.close - rawData[i-1].close) / rawData[i-1].close * 100
          chgStr = chg.toFixed(2) + '%'
        }
        return `<div style="font-weight:bold; margin-bottom:5px;">${item.date.substring(5, 16)}</div>
          开: ${item.open} | 收: <span style="color:${item.close >= item.open ? color.up : color.down}">${item.close}</span><br/>
          幅: <span style="color:${parseFloat(chgStr) >= 0 ? color.up : color.down}">${chgStr}</span> | 量: ${item.volume}`
      }
    },
    axisPointer: { link: { xAxisIndex: 'all' } },
    grid: [
      { left: '12%', right: '8%', top: '10%', height: '55%' },
      { left: '12%', right: '8%', top: '75%', height: '15%' }
    ],
    xAxis: [
      {
        type: 'category',
        data: categoryData,
        scale: true,
        boundaryGap: false,
        axisLine: { show: false }, // 🟢 隐藏主图下边框线（消除红框直线）
        axisTick: { show: false },
        axisLabel: { show: false },
        splitLine: { show: true, lineStyle: { type: 'dashed', opacity: 0.1 } },
        min: 'dataMin', max: 'dataMax'
      },
      {
        type: 'category',
        gridIndex: 1,
        data: categoryData,
        scale: true,
        boundaryGap: false,
        axisLine: { onZero: false },
        axisTick: { show: false },
        splitLine: { show: false },
        axisLabel: { show: true, color: '#666', fontSize: 10 },
        min: 'dataMin', max: 'dataMax'
      }
    ],
    yAxis: [
      { scale: true, splitLine: { show: true, lineStyle: { type: 'dashed', opacity: 0.1 } } },
      { scale: true, gridIndex: 1, splitNumber: 2, axisLabel: { show: false }, axisLine: { show: false }, splitLine: { show: false } }
    ],
    dataZoom: [
      {
        type: 'inside',
        xAxisIndex: [0, 1],
        startValue: finalStartValue,
        endValue: finalEndValue,
        rangeMode: ['value', 'value']
      },
      {
        show: true,
        type: 'slider',
        xAxisIndex: [0, 1],
        top: '92%',
        height: 20,
        startValue: finalStartValue,
        endValue: finalEndValue,
        borderColor: 'transparent',
        backgroundColor: '#f5f7fa',
        handleStyle: { color: '#666' }
      }
    ],
    series: [
      {
        name: 'K线',
        type: 'candlestick',
        data: kData,
        itemStyle: { color: color.up, color0: color.down, borderColor: color.up, borderColor0: color.down }
      },
      {
        name: '成交量',
        type: 'bar',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: volData
      }
    ]
  }

  myChart.setOption(option, false)
}

watch(() => props.data, () => { nextTick(render) }, { deep: true })
onMounted(() => { nextTick(render) })
onBeforeUnmount(() => { if (myChart) myChart.dispose() })
</script>

<style scoped>
.chart-wrapper { width: 100%; position: relative; background: #fff; }
.echart-box { width: 100%; height: 480px; }
</style>