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
let isZoomInitialized = false

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

  // 1. 无数据时的处理
  if (rawData.length === 0) {
    isZoomInitialized = false // 重置缩放状态
    myChart.setOption({
      title: {
        show: true, // 显式开启
        text: '暂无数据',
        left: 'center',
        top: 'center',
        textStyle: { color: '#ccc' }
      },
      grid: [], xAxis: [], yAxis: [], series: []
    }, true) // true = 不合并，彻底重置
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
      itemStyle: { color: item.close >= item.open ? color.volUp : color.volDown }
    })
  })

  // 2. 构建 Option
  const option = {
    // 🟢 关键修复1：强制隐藏标题，解决文字残留
    title: { show: false },
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
        let prevClose = item.open
        if (i > 0) prevClose = rawData[i - 1].close
        if (prevClose !== 0) {
          const chg = (item.close - prevClose) / prevClose * 100
          chgStr = chg.toFixed(2) + '%'
        }
        return `<div style="font-weight:bold; margin-bottom:5px;">${item.date.substring(5, 16)}</div>
          开: ${item.open} | 收: <span style="color:${item.close >= item.open ? color.up : color.down}">${item.close}</span><br/>
          幅: <span style="color:${parseFloat(chgStr) >= 0 ? color.up : color.down}">${chgStr}</span> | 量: ${item.volume}`
      }
    },
    axisPointer: { link: { xAxisIndex: 'all' } },
    grid: [
      { left: '12%', right: '5%', top: '10%', height: '55%' },
      { left: '12%', right: '5%', top: '75%', height: '15%' }
    ],
    xAxis: [
      {
        type: 'category',
        data: categoryData,
        scale: true,
        boundaryGap: false,
        // 🟢 关键修复2：除了隐藏线(axisLine)，必须同时隐藏刻度(axisTick)
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { show: false },
        splitLine: { show: true, lineStyle: { type: 'dashed', opacity: 0.2 } },
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
      { scale: true, splitLine: { show: true, lineStyle: { type: 'dashed', opacity: 0.2 } } },
      { scale: true, gridIndex: 1, splitNumber: 2, axisLabel: { show: false }, axisLine: { show: false }, splitLine: { show: false } }
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

  // 3. 缩放逻辑
  if (!isZoomInitialized) {
    const totalLen = categoryData.length
    const SHOW_COUNT = 60
    const startValue = Math.max(0, totalLen - SHOW_COUNT)
    const endValue = totalLen - 1

    option.dataZoom = [
      {
        type: 'inside',
        xAxisIndex: [0, 1],
        startValue: startValue,
        endValue: endValue
      },
      {
        show: true,
        type: 'slider',
        xAxisIndex: [0, 1],
        top: '92%',
        height: 20,
        startValue: startValue,
        endValue: endValue,
        borderColor: 'transparent',
        backgroundColor: '#f5f7fa',
        handleStyle: { color: '#666' }
      }
    ]

    myChart.setOption(option, true)
    isZoomInitialized = true
  } else {
    // 仅更新数据，保留用户当前的缩放位置
    myChart.setOption(option, false)
  }
}

watch(() => props.data, () => { nextTick(render) }, { deep: true })
onMounted(() => { nextTick(render) })
onBeforeUnmount(() => { if (myChart) myChart.dispose() })
</script>

<style scoped>
.chart-wrapper { width: 100%; position: relative; background: #fff; }
.echart-box { width: 100%; height: 480px; }
</style>