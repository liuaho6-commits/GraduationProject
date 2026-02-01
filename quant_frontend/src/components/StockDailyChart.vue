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
// 🟢 关键标志位：是否已经初始化过缩放
let isZoomInitialized = false

// 颜色配置
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

  if (rawData.length === 0) {
    // 无数据时显示提示
    myChart.setOption({
      title: { text: '暂无数据', left: 'center', top: 'center', textStyle: { color: '#ccc' } },
      grid: [], xAxis: [], yAxis: [], series: []
    })
    return
  }

  // 1. 数据转换
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

  // 2. 构建基础 Option (不包含 dataZoom 的动态值)
  const option = {
    animation: false, // 禁用动画，防止高频刷新闪烁
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      backgroundColor: 'rgba(255, 255, 255, 0.95)',
      borderWidth: 1,
      borderColor: '#eee',
      padding: 10,
      textStyle: { color: '#333', fontSize: 12 },
      formatter: (params) => {
        const kParam = params.find(p => p.seriesName === 'K线')
        if (!kParam) return ''
        const i = kParam.dataIndex
        const item = rawData[i]
        if (!item) return ''

        let chgStr = '0.00%'
        let prevClose = item.open
        if (i > 0) prevClose = rawData[i - 1].close
        if (prevClose !== 0) {
          const chg = (item.close - prevClose) / prevClose * 100
          chgStr = chg.toFixed(2) + '%'
        }
        const isUp = parseFloat(chgStr) >= 0

        return `
          <div style="font-weight:bold; margin-bottom:5px;">${item.date.substring(5, 16)}</div>
          开: ${item.open} <br/>
          收: <span style="color:${item.close >= item.open ? color.up : color.down}">${item.close}</span> <br/>
          高: ${item.high} <br/>
          低: ${item.low} <br/>
          幅: <span style="color:${isUp ? color.up : color.down}">${chgStr}</span> <br/>
          量: ${item.volume}
        `
      }
    },
    axisPointer: { link: { xAxisIndex: 'all' }, label: { backgroundColor: '#777' } },
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
        axisLine: { onZero: false },
        splitLine: { show: true, lineStyle: { type: 'dashed', opacity: 0.2 } },
        axisLabel: { show: false },
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

  // 3. 🟢 关键修复：只在第一次渲染时锁定视角
  if (!isZoomInitialized) {
    const totalLen = categoryData.length
    const SHOW_COUNT = 60
    const startValue = Math.max(0, totalLen - SHOW_COUNT)
    const endValue = totalLen - 1

    // 只有第一次，我们才注入 dataZoom 的 startValue/endValue
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

    // 第一次：不合并 (true)，彻底重置
    myChart.setOption(option, true)
    isZoomInitialized = true

  } else {
    // 🟢 后续更新：只更新数据
    // 我们不传 dataZoom 属性，ECharts 会自动保留当前的缩放位置
    // 参数 false 代表“合并模式”，只更新变动的部分 (data)
    myChart.setOption(option, false)
  }
}

watch(() => props.data, () => {
  nextTick(render)
}, { deep: true })

onMounted(() => {
  nextTick(render)
})

onBeforeUnmount(() => {
  if (myChart) myChart.dispose()
})
</script>

<style scoped>
.chart-wrapper {
  width: 100%;
  position: relative;
  background: #fff;
}
.echart-box {
  width: 100%;
  height: 480px;
}
</style>