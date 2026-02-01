<template>
  <div ref="chartRef" style="width: 100%; height: 350px;"></div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import * as echarts from 'echarts'
import axios from 'axios'

const chartRef = ref(null)
let myChart = null
let timer = null

const initChart = () => {
  if (chartRef.value) {
    myChart = echarts.init(chartRef.value)
    const option = {
      tooltip: {
        trigger: 'axis',
        formatter: '{b}<br/>日内收益: <b>{c}%</b>', // {b}即为时间字符串
        axisPointer: { type: 'cross' }
      },
      grid: { left: '2%', right: '3%', bottom: '5%', top: '10%', containLabel: true },
      xAxis: {
        type: 'category', // 【关键】强制为类目轴，禁止时间解析
        data: [],
        boundaryGap: false,
        axisLine: { lineStyle: { color: '#666' } }
      },
      yAxis: {
        type: 'value',
        scale: true,
        axisLabel: { formatter: '{value} %', color: '#666' },
        splitLine: { show: true, lineStyle: { type: 'dashed', color: '#eee' } }
      },
      series: [{
        name: '分时收益',
        type: 'line',
        smooth: true,
        symbol: 'none',
        itemStyle: { color: '#E55555' },
        areaStyle: {
           color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(229, 85, 85, 0.2)' },
            { offset: 1, color: 'rgba(229, 85, 85, 0.0)' }
          ])
        },
        data: []
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
    const res = await axios.get('http://127.0.0.1:8000/trade/api/performance/?type=intraday', {
      headers: { 'Authorization': `Token ${token}` }
    })

    if (res.data.code === 200) {
      const data = res.data.data || []
      // 直接使用字符串，ECharts 不会自作聪明添加日期
      const times = data.map(i => i.time)
      const values = data.map(i => i.total_return_rate)

      if (values.length > 0) {
          const maxVal = Math.max(...values, 0)
          const minVal = Math.min(...values, 0)
          const absLimit = Math.max(Math.abs(maxVal), Math.abs(minVal)) * 1.2

          myChart.setOption({
            xAxis: { data: times },
            yAxis: { min: -absLimit, max: absLimit },
            series: [{ data: values }]
          })
      }
    }
  } catch (e) {
    console.error("分时图错误", e)
  }
}

onMounted(() => {
  initChart()
  fetchData()
  timer = setInterval(fetchData, 1000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
  window.removeEventListener('resize', resizeChart)
  if(myChart) myChart.dispose()
})
</script>