<template>
  <div ref="chartRef" style="width: 100%; height: 350px;"></div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import * as echarts from 'echarts'
import axios from 'axios'

const chartRef = ref(null)
let myChart = null
let timer = null // 🟢 定义定时器变量

// 初始化图表 (骨架)
const initChart = () => {
  if (chartRef.value) {
    myChart = echarts.init(chartRef.value)

    const option = {
      tooltip: {
        trigger: 'axis',
        formatter: '{b}<br/>日内收益: <b>{c}%</b>',
        axisPointer: { type: 'cross' }
      },
      grid: {
        left: '2%', right: '3%', bottom: '5%', top: '10%', containLabel: true
      },
      xAxis: {
        type: 'category',
        data: [], // 初始为空
        boundaryGap: false,
        axisLine: { lineStyle: { color: '#666' } }
      },
      yAxis: {
        type: 'value',
        scale: true,
        axisLabel: { formatter: '{value} %', color: '#666' },
        splitLine: { show: true, lineStyle: { type: 'dashed', color: '#eee' } }
      },
      series: [
        {
          name: '分时收益',
          type: 'line',
          smooth: true,
          symbol: 'none',
          itemStyle: { color: '#E55555' },
          lineStyle: { width: 2 },
          areaStyle: {
             color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: 'rgba(229, 85, 85, 0.2)' },
              { offset: 1, color: 'rgba(229, 85, 85, 0.0)' }
            ])
          },
          data: [], // 初始为空
          // 添加一条 0 轴基准线，方便看涨跌
          markLine: {
            symbol: 'none',
            data: [{ yAxis: 0, label: { show: false }, lineStyle: { color: '#999', type: 'dotted' } }]
          }
        }
      ]
    }
    myChart.setOption(option)
    window.addEventListener('resize', resizeChart)
  }
}

const resizeChart = () => myChart && myChart.resize()

// 获取数据并更新图表
const fetchData = async () => {
  try {
    const token = localStorage.getItem('token')
    // 🟢 每秒调用这个接口
    const res = await axios.get('http://127.0.0.1:8000/trade/api/performance/?type=intraday', {
      headers: { 'Authorization': `Token ${token}` }
    })

    if (res.data.code === 200) {
      const data = res.data.data || []
      const times = data.map(i => i.time)
      const values = data.map(i => i.total_return_rate)

      // 自动计算 Y 轴范围，防止线条跑出去了
      if (values.length > 0) {
          const maxVal = Math.max(...values, 0)
          const minVal = Math.min(...values, 0)
          // 稍微留点余量 (1.2倍)
          const absLimit = Math.max(Math.abs(maxVal), Math.abs(minVal)) * 1.2

          // 增量更新数据，图表不会闪烁
          myChart.setOption({
            xAxis: { data: times },
            yAxis: { min: -absLimit, max: absLimit }, // 动态调整 Y 轴让 0 居中 (可选)
            series: [{ data: values }]
          })
      }
    }
  } catch (e) {
    console.error("分时图更新失败", e)
  }
}

onMounted(() => {
  initChart()
  fetchData() // 立即执行一次

  // 🟢 启动定时器：每 1000ms (1秒) 刷新一次
  timer = setInterval(fetchData, 1000)
})

onUnmounted(() => {
  // 🟢 销毁组件时必须清除定时器，否则后台会一直请求
  if (timer) clearInterval(timer)

  window.removeEventListener('resize', resizeChart)
  if(myChart) myChart.dispose()
})
</script>