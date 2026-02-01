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

// 颜色配置
const color = {
  up: '#F56C6C',
  down: '#00C853',
  volUp: '#F56C6C',
  volDown: '#00C853'
}

const render = () => {
  if (!chartContainer.value) return

  // 1. 初始化
  if (!myChart) {
    myChart = echarts.init(chartContainer.value)
    window.addEventListener('resize', () => myChart && myChart.resize())
  }

  const rawData = props.data || []
  if (rawData.length === 0) {
    myChart.setOption({
      title: { text: '暂无数据', left: 'center', top: 'center', textStyle: { color: '#ccc' } },
      grid: [], xAxis: [], yAxis: [], series: []
    })
    return
  }

  // 2. 数据转换
  const categoryData = []
  const kData = []
  const volData = []

  rawData.forEach(item => {
    // 格式化时间
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

  // ==========================================
  // 🟢 智能缩放锁定逻辑 (核心修复)
  // ==========================================
  const totalLen = categoryData.length
  const DEFAULT_WINDOW_SIZE = 60 // 默认看60根

  let finalStartValue = 0
  let finalEndValue = totalLen - 1

  // 检查是否是“第一次渲染”或者“无图表状态”
  // 通过 getOption() 获取当前的缩放情况
  const currentOpt = myChart.getOption()

  // 默认策略：如果还没初始化，就锁定在最新
  let shouldSnapToEnd = true
  let currentWindowSize = DEFAULT_WINDOW_SIZE

  if (currentOpt && currentOpt.dataZoom && currentOpt.dataZoom.length > 0) {
    // 获取当前的 dataZoom 状态
    const zoomState = currentOpt.dataZoom[0]

    // 判断用户是否正在看“最右边”
    // zoomState.end 是百分比 (0-100)。如果大于 98%，我们认为用户想跟随最新数据
    if (zoomState.end != null && zoomState.end < 98) {
      shouldSnapToEnd = false
    }

    // 计算用户当前的窗口大小 (看了多少根K线)
    // 优先使用 startValue/endValue (索引)，比百分比更准
    const sVal = zoomState.startValue
    const eVal = zoomState.endValue

    if (typeof sVal === 'number' && typeof eVal === 'number') {
      currentWindowSize = eVal - sVal
      if (currentWindowSize < 5) currentWindowSize = 5 // 最小保护
    }
  }

  // 计算新的 start/end
  if (shouldSnapToEnd) {
    // A. 锁定模式：永远显示最新的 N 根
    finalEndValue = totalLen - 1
    finalStartValue = Math.max(0, finalEndValue - currentWindowSize)
  } else {
    // B. 历史模式：保持索引不变 (用户在看历史，别乱动)
    // 我们直接沿用之前的 startValue/endValue
    // 注意：如果数据是追加的，索引不变意味着看到的还是那段历史时间，符合直觉
    if (currentOpt && currentOpt.dataZoom && currentOpt.dataZoom[0]) {
       finalStartValue = currentOpt.dataZoom[0].startValue
       finalEndValue = currentOpt.dataZoom[0].endValue
    }
  }

  // ==========================================

  const option = {
    animation: false, // 必须禁用动画，否则高频刷新会闪
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
      },
      position: function (pos, params, el, elRect, size) {
         const obj = { top: 10 };
         obj[['left', 'right'][+(pos[0] < size.viewSize[0] / 2)]] = 30;
         return obj;
      }
    },
    axisPointer: { link: { xAxisIndex: 'all' }, label: { backgroundColor: '#777' } },
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
    // 显式传入计算好的 startValue / endValue
    dataZoom: [
      {
        type: 'inside',
        xAxisIndex: [0, 1],
        startValue: finalStartValue,
        endValue: finalEndValue,
        rangeMode: ['value', 'value'] // 🟢 强制使用 value 模式，防止百分比漂移
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

  // 使用 false (merge模式)，但因为我们显式指定了 dataZoom，所以不会丢失位置
  myChart.setOption(option, false)
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