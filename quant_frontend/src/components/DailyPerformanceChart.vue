<template>
  <div ref="chartRef" style="width: 100%; height: 350px;"></div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import * as echarts from 'echarts'
import axios from 'axios'

const chartRef = ref(null)
let myChart = null

const initChart = (dates, values) => {
  if (chartRef.value) {
    myChart = echarts.init(chartRef.value)

    // 初始缩放计算
    const totalPoints = dates.length
    let startPercent = 0
    if (totalPoints > 100) {
      startPercent = ((totalPoints - 100) / totalPoints) * 100
    }

    const option = {
      tooltip: {
        trigger: 'axis',
        formatter: '{b}<br/>累计收益率: <b>{c}%</b>'
      },
      grid: {
        left: '2%', right: '3%', bottom: '15%', top: '10%', containLabel: true
      },
      xAxis: {
        type: 'category',
        data: dates,
        boundaryGap: false,
        axisLine: { lineStyle: { color: '#666' } }
      },
      yAxis: {
        type: 'value',
        scale: true,
        axisLabel: { formatter: '{value} %', color: '#666' },
        splitLine: { show: true, lineStyle: { type: 'dashed', color: '#eee' } }
      },
      dataZoom: [
        { type: 'slider', show: true, start: startPercent, end: 100, bottom: 5, height: 20 },
        { type: 'inside', start: startPercent, end: 100 }
      ],
      series: [
        {
          name: '累计收益率',
          type: 'line',
          smooth: 0.6,
          symbol: 'none',
          showSymbol: false,
          itemStyle: { color: '#E55555' },
          lineStyle: { width: 3, shadowColor: 'rgba(229, 85, 85, 0.3)', shadowBlur: 10 },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: 'rgba(229, 85, 85, 0.4)' },
              { offset: 1, color: 'rgba(229, 85, 85, 0.01)' }
            ])
          },
          data: values
        }
      ]
    }
    myChart.setOption(option)
    window.addEventListener('resize', resizeChart)
  }
}

const resizeChart = () => myChart && myChart.resize()

const fetchData = async () => {
  try {
    const token = localStorage.getItem('token')
    const res = await axios.get('http://127.0.0.1:8000/trade/api/performance/?type=daily', {
      headers: { 'Authorization': `Token ${token}` }
    })
    if (res.data.code === 200) {
      const data = res.data.data || []
      const dates = data.map(i => i.date)
      const values = data.map(i => i.total_return_rate)
      initChart(dates, values)
    }
  } catch (e) {
    console.error(e)
  }
}

onMounted(fetchData)
onUnmounted(() => {
  window.removeEventListener('resize', resizeChart)
  if(myChart) myChart.dispose()
})
</script>