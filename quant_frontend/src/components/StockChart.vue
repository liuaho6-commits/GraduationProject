<template>
  <div ref="chartContainer" class="kline-chart"></div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  data: { type: Array, default: () => [] },
  freq: { type: String, default: 'daily' } // 'daily' | 'min'
})

const chartContainer = ref(null)
let myChart = null

const render = () => {
  if (!chartContainer.value) return
  if (!myChart) myChart = echarts.init(chartContainer.value)

  const rawData = props.data
  let xAxisData = [], kLineData = [], volData = []

  // 🎨 颜色配置
  const upColor = '#F56C6C'; const downColor = '#00C853'

  try {
      if (props.freq === 'daily') {
          // --- 日线模式 ---
          xAxisData = rawData.map(item => item.date)
          kLineData = rawData.map(item => [item.open, item.close, item.low, item.high])
          volData = rawData.map(item => item.volume)
      } else {
          // --- 分时模式 ---
          // 安全处理：防止 rawData 为空或格式不对
          if (rawData.length > 0) {
              xAxisData = rawData.map(item => {
                  // 尝试提取时间 "09:30"
                  const parts = item.date.split(' ')
                  return parts.length > 1 ? parts[1].substring(0, 5) : item.date
              })
              kLineData = rawData.map(item => [item.open, item.close, item.low, item.high])
              volData = rawData.map(item => item.volume)
          }
      }
  } catch (e) {
      console.warn("图表数据解析异常:", e)
  }

  const option = {
    animation: false,
    grid: [
      { left: '50', right: '20', top: '30', height: '60%' },
      { left: '50', right: '20', top: '75%', height: '15%' }
    ],
    tooltip: {
        trigger: 'axis', axisPointer: { type: 'cross' },
        formatter: (params) => {
            if (!params[0]) return ''
            const k = params[0]
            if (!k.value || k.value.length < 2) return ''
            return `${k.axisValue}<br/>开:${k.value[1]} 高:${k.value[4]}<br/>低:${k.value[3]} 收:${k.value[2]}`
        }
    },
    xAxis: [
      {
        type: 'category', data: xAxisData, boundaryGap: false,
        axisLine: { onZero: false },
        // 分时图强制固定X轴，实现"未开盘留白"效果
        min: props.freq === 'min' ? 0 : undefined,
        max: props.freq === 'min' ? 48 : undefined
      },
      { type: 'category', gridIndex: 1, data: xAxisData, axisLabel: { show: false } }
    ],
    yAxis: [
      { scale: true, splitLine: { show: true, lineStyle: { type: 'dashed' } } },
      { scale: true, gridIndex: 1, splitLine: { show: false }, axisLabel: { show: false } }
    ],
    dataZoom: [
        { type: 'inside', disabled: props.freq === 'min' },
        { show: props.freq === 'daily', type: 'slider', top: '92%' }
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
                const i = params.dataIndex;
                // 安全获取 K线数据
                const k = kLineData[i]
                if (!k) return upColor
                return (k[1] > k[0]) ? upColor : downColor
            }
        }
      }
    ]
  }

  myChart.setOption(option, true)
}

// 🟢 关键修复：同时监听 data 和 freq
watch([() => props.data, () => props.freq], () => {
    nextTick(render)
}, { deep: true })

onMounted(() => {
    window.addEventListener('resize', () => myChart && myChart.resize())
})
onBeforeUnmount(() => {
    if (myChart) myChart.dispose()
})
</script>

<style scoped>
.kline-chart { width: 100%; height: 600px; }
</style>