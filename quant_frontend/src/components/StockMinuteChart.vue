<template>
  <div ref="chartContainer" className="chart-container"></div>
</template>

<script setup>
import {ref, onMounted, onBeforeUnmount, watch, nextTick} from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  data: {type: Array, default: () => []},
  preClose: {type: Number, default: 0} // 🟢 接收昨收价
})

const chartContainer = ref(null)
let myChart = null
const isFirstRender = ref(true)

const generateDefaultTimeline = () => {
  const timeline = []
  let h = 9, m = 30
  for (let i = 0; i < 24; i++) {
    timeline.push(`${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}`)
    m += 5
    if (m >= 60) {
      h++;
      m = 0
    }
  }
  h = 13;
  m = 0
  for (let i = 0; i < 24; i++) {
    timeline.push(`${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}`)
    m += 5
    if (m >= 60) {
      h++;
      m = 0
    }
  }
  return timeline
}

const render = () => {
  if (!chartContainer.value) return
  if (!myChart) myChart = echarts.init(chartContainer.value)

  const rawData = props.data || []
  const hasData = rawData.length > 0
  const upColor = '#F56C6C';
  const downColor = '#00C853'

  let xAxisData = []
  let kLineData = []
  let volData = []

  if (hasData) {
    xAxisData = rawData.map(item => {
      let t = item.date
      if (t.includes(' ')) t = t.split(' ')[1]
      else if (t.includes('T')) t = t.split('T')[1]
      return t && t.length >= 5 ? t.substring(0, 5) : t
    })

    const realK = rawData.map(item => [item.open, item.close, item.low, item.high])
    const realV = rawData.map(item => item.volume)

    const WINDOW_SIZE = 48
    if (xAxisData.length < WINDOW_SIZE) {
      const padCount = WINDOW_SIZE - xAxisData.length
      const padX = new Array(padCount).fill('')
      xAxisData = [...xAxisData, ...padX]
      kLineData = realK
      volData = realV
    } else {
      kLineData = realK
      volData = realV
    }
  } else {
    xAxisData = generateDefaultTimeline()
    kLineData = []
    volData = []
  }

  const dataLen = xAxisData.length
  let startValue = Math.max(0, dataLen - 50)
  let endValue = dataLen - 1

  if (!isFirstRender.value && hasData && myChart) {
    const currentOpt = myChart.getOption()
    if (currentOpt && currentOpt.dataZoom && currentOpt.dataZoom.length > 0) {
      const dz = currentOpt.dataZoom[0]
      const prevStart = dz.startValue
      const prevEnd = dz.endValue

      if (dz.end > 99) {
        const span = prevEnd - prevStart
        endValue = dataLen - 1
        startValue = Math.max(0, endValue - span)
      } else {
        startValue = Math.min(prevStart, dataLen - 1)
        endValue = Math.min(prevEnd, dataLen - 1)
      }
    }
  }

  if (hasData) {
    isFirstRender.value = false
  }

  const option = {
    animation: false,
    title: {
      show: !hasData,
      text: '等待开盘数据...',
      left: 'center', top: 'center',
      textStyle: {color: '#ccc', fontSize: 14}
    },
    grid: [
      {left: '50', right: '20', top: '20', height: '60%'},
      {left: '50', right: '20', top: '68%', height: '16%'}
    ],
    tooltip: {
      trigger: 'axis', axisPointer: {type: 'cross'},
      formatter: (params) => {
        if (!params[0] || !params[0].value) return ''
        const k = params[0]
        if (!Array.isArray(k.value) || k.value.length < 2) return ''

        const open = k.value[1]
        const currentClose = k.value[2]
        const color = currentClose >= open ? upColor : downColor

        // 🟢 修正计算：(当前价 - 昨收) / 昨收
        // 这种方式是标准的证券涨跌幅计算
        let chgPercent = 0
        const basePrice = props.preClose

        if (basePrice && basePrice !== 0) {
          chgPercent = (currentClose - basePrice) / basePrice * 100
        } else if (open !== 0) {
          // 如果没有昨收价，兜底用当前K线开盘价（尽量避免这种情况）
          chgPercent = (currentClose - open) / open * 100
        }

        const chgColor = chgPercent >= 0 ? upColor : downColor

        return `
                <div style="font-weight:bold; margin-bottom:5px;">${k.axisValue}</div>
                开盘: ${open}<br/>
                最高: ${k.value[4]}<br/>
                最低: ${k.value[3]}<br/>
                收盘: <span style="color:${color}; font-weight:bold">${currentClose}</span><br/>
                涨跌: <span style="color:${chgColor}">${chgPercent.toFixed(2)}%</span>
            `
      }
    },
    xAxis: [
      {
        type: 'category', data: xAxisData, boundaryGap: false,
        axisLine: {onZero: false},
        axisLabel: {show: true, interval: 'auto'},
        min: 'dataMin', max: 'dataMax'
      },
      {type: 'category', gridIndex: 1, data: xAxisData, axisLabel: {show: false}}
    ],
    yAxis: [
      {scale: true, splitLine: {show: true, lineStyle: {type: 'dashed'}}, axisLabel: {show: hasData}},
      {scale: true, gridIndex: 1, splitLine: {show: false}, axisLabel: {show: false}}
    ],
    dataZoom: [
      {
        type: 'inside', xAxisIndex: [0, 1],
        startValue: startValue,
        endValue: endValue
      },
      {
        show: true, type: 'slider', xAxisIndex: [0, 1],
        top: '88%', height: 20, handleSize: '100%',
        startValue: startValue,
        endValue: endValue
      }
    ],
    series: [
      {
        name: 'K线', type: 'candlestick', data: kLineData,
        itemStyle: {color: upColor, color0: downColor, borderColor: upColor, borderColor0: downColor}
      },
      {
        name: '成交量', type: 'bar', xAxisIndex: 1, yAxisIndex: 1, data: volData,
        itemStyle: {
          color: (params) => {
            const k = kLineData[params.dataIndex]
            if (!k) return upColor
            return (k[1] > k[0]) ? upColor : downColor
          }
        }
      }
    ]
  }

  myChart.setOption(option, true)
}

// 🟢 监听 preClose 变化，确保异步获取的昨收价能更新图表
watch([() => props.data, () => props.preClose], () => {
  nextTick(render)
}, {deep: true})

onMounted(() => {
  isFirstRender.value = true
  window.addEventListener('resize', () => myChart && myChart.resize())
  setTimeout(render, 50)
})

onBeforeUnmount(() => {
  if (myChart) myChart.dispose()
})
</script>

<style scoped>
.chart-container {
  width: 100%;
  height: 600px;
}
</style>