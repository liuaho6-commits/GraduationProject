<template>
  <div ref="chartContainer" class="chart-container"></div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  data: { type: Array, default: () => [] }
})

const emits = defineEmits(['click-item'])

const chartContainer = ref(null)
let myChart = null

const render = () => {
  if (!chartContainer.value) return
  if (!myChart) {
    myChart = echarts.init(chartContainer.value)
    myChart.on('click', (params) => {
        if (params.componentType === 'series') {
            emits('click-item', params.name)
        }
    })
  }

  const rawData = props.data || []
  let xAxisData = [], kLineData = [], volData = []

  // 🟢 预先获取最新价格（用于计算“持有至今”的收益）
  let latestClose = 0
  if (rawData.length > 0) {
      xAxisData = rawData.map(item => item.date)
      kLineData = rawData.map(item => [item.open, item.close, item.low, item.high])
      volData = rawData.map(item => item.volume)
      latestClose = rawData[rawData.length - 1].close
  }

  const upColor = '#F56C6C'; const downColor = '#00C853'

  const option = {
    animation: false,
    grid: [
      { left: '50', right: '20', top: '30', height: '60%' },
      { left: '50', right: '20', top: '75%', height: '15%' }
    ],
    tooltip: {
        trigger: 'axis', axisPointer: { type: 'cross' },
        formatter: (params) => {
            const k = params[0]
            if (!k || !k.value || k.value.length < 2) return ''

            const i = k.dataIndex
            const item = rawData[i]
            const close = item.close
            const open = item.open

            // 1. 当日涨跌幅 (相比昨日)
            let dailyChg = 0
            if (i > 0) {
                const prevClose = rawData[i - 1].close
                dailyChg = (close - prevClose) / prevClose * 100
            } else {
                dailyChg = (close - open) / open * 100
            }

            // 🟢 2. 修正后的“至今”涨跌幅
            // 逻辑：(最新价 - 当时买入价) / 当时买入价
            // 这样“山顶”买入就是亏，“抄底”买入就是赚
            let holdUntilNowChg = 0
            if (close !== 0) {
                holdUntilNowChg = (latestClose - close) / close * 100
            }

            const colorDaily = dailyChg >= 0 ? upColor : downColor
            const colorHold = holdUntilNowChg >= 0 ? upColor : downColor

            return `
                <div style="font-weight:bold; margin-bottom:5px;">${k.axisValue}</div>
                开盘: ${open} <br/>
                最高: ${k.value[4]} <br/>
                最低: ${k.value[3]} <br/>
                收盘: <span style="color:${close >= open ? upColor : downColor}; font-weight:bold">${close}</span> <br/>
                <hr style="margin:5px 0; border:0; border-top:1px dashed #666;" />
                当日: <span style="color:${colorDaily}">${dailyChg.toFixed(2)}%</span> <br/>
                至今: <span style="color:${colorHold}">${holdUntilNowChg.toFixed(2)}%</span>
            `
        }
    },
    xAxis: [
      { type: 'category', data: xAxisData, boundaryGap: false, axisLine: { onZero: false } },
      { type: 'category', gridIndex: 1, data: xAxisData, axisLabel: { show: false } }
    ],
    yAxis: [
      { scale: true, splitLine: { show: true, lineStyle: { type: 'dashed' } } },
      { scale: true, gridIndex: 1, splitLine: { show: false }, axisLabel: { show: false } }
    ],
    dataZoom: [
        { type: 'inside', start: 50, end: 100 },
        { show: true, type: 'slider', top: '92%', start: 50, end: 100 }
    ],
    series: [
      {
        name: 'K线', type: 'candlestick', data: kLineData,
        itemStyle: { color: upColor, color0: downColor, borderColor: upColor, borderColor0: downColor }
      },
      {
        name: '成交量', type: 'bar', xAxisIndex: 1, yAxisIndex: 1, data: volData,
        itemStyle: {
            color: (params) => {
                const k = kLineData[params.dataIndex]
                return (k && k[1] > k[0]) ? upColor : downColor
            }
        }
      }
    ]
  }
  myChart.setOption(option, true)
}

watch(() => props.data, () => { nextTick(render) }, { deep: true })

onMounted(() => {
    window.addEventListener('resize', () => myChart && myChart.resize())
    setTimeout(render, 50)
})

onBeforeUnmount(() => { if (myChart) myChart.dispose() })
</script>

<style scoped>
.chart-container { width: 100%; height: 600px; }
</style>