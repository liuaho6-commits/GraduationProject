<template>
  <div ref="chartRef" style="width: 100%; height: 350px;"></div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import axios from 'axios'

const chartRef = ref(null)
let myChart = null

const initChart = async (dates, values) => {
  await nextTick()
  if (chartRef.value) {
    if (chartRef.value.clientWidth === 0) {
        setTimeout(() => initChart(dates, values), 50)
        return
    }
    if (myChart) myChart.dispose()
    myChart = echarts.init(chartRef.value)

    const totalPoints = dates.length
    let startPercent = 0
    if (totalPoints > 60) {
      startPercent = ((totalPoints - 60) / totalPoints) * 100
    }

    const option = {
      tooltip: {
        trigger: 'axis',
        formatter: (params) => {
          const item = params[0];
          // 直接显示 x 轴的文本（即后端传来的日期字符串）
          return `${item.name}<br/>累计收益率: <b>${parseFloat(item.value).toFixed(2)}%</b>`;
        }
      },
      grid: { left: '2%', right: '3%', bottom: '15%', top: '10%', containLabel: true },
      xAxis: {
        type: 'category', // 【关键】改为 Category
        data: dates,      // 直接传入 ["2025-07-11", "2025-07-12"]
        boundaryGap: false,
        axisLine: { lineStyle: { color: '#666' } }
      },
      yAxis: {
        type: 'value',
        scale: true,
        axisLabel: { formatter: (v) => v.toFixed(2) + ' %', color: '#666' },
        splitLine: { show: true, lineStyle: { type: 'dashed', color: '#eee' } }
      },
      dataZoom: [
        { type: 'slider', show: true, start: startPercent, end: 100, bottom: 5, height: 20 },
        { type: 'inside', start: startPercent, end: 100 }
      ],
      series: [{
        name: '累计收益率',
        type: 'line',
        smooth: 0.6,
        symbol: 'none',
        itemStyle: { color: '#E55555' },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(229, 85, 85, 0.4)' },
            { offset: 1, color: 'rgba(229, 85, 85, 0.01)' }
          ])
        },
        data: values
      }]
    }
    myChart.setOption(option)
    window.addEventListener('resize', resizeChart)
  }
}

const resizeChart = () => myChart && myChart.resize()

const fetchData = async () => {
  try {
    const token = localStorage.getItem('token')
    if (!token) return
    const res = await axios.get('http://127.0.0.1:8000/trade/api/performance/?type=daily', {
      headers: { 'Authorization': `Token ${token}` }
    })

    if (res.data.code === 200) {
      const data = res.data.data || []
      const dates = data.map(i => i.date) // 拿到纯字符串
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