<template>
  <div style="position: relative; width: 100%; height: 350px;">
    <div v-if="isHoliday" class="no-data-overlay">
      <span class="no-data-text">今日为休市日或非交易时间，暂无分时数据</span>
    </div>

    <div ref="chartRef" style="width: 100%; height: 100%;" :style="{ opacity: isHoliday ? 0 : 1 }"></div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import * as echarts from 'echarts'
import axios from 'axios'

const chartRef = ref(null)
const isHoliday = ref(false) // 控制是否显示节假日遮罩
let myChart = null
let timer = null

const initChart = () => {
  if (chartRef.value) {
    myChart = echarts.init(chartRef.value)
    const option = {
      tooltip: {
        trigger: 'axis',
        formatter: '{b}<br/>日内收益: <b>{c}%</b>',
        axisPointer: { type: 'cross' }
      },
      grid: { left: '2%', right: '3%', bottom: '5%', top: '10%', containLabel: true },
      xAxis: {
        type: 'category',
        data: [],
        boundaryGap: false,
        axisLine: { lineStyle: { color: '#666' } }
      },
      yAxis: {
        type: 'value',
        scale: true,
        axisLabel: {
          formatter: (value) => value.toFixed(2) + ' %',
          color: '#666'
        },
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

      // 核心拦截逻辑：如果数据为空，触发休市遮罩
      if (data.length === 0) {
        isHoliday.value = true
        return
      }

      // 有数据则关闭遮罩，正常渲染
      isHoliday.value = false

      const times = data.map(i => i.time)
      const values = data.map(i => i.total_return_rate)

      const maxVal = Math.max(...values, 0)
      const minVal = Math.min(...values, 0)
      let absLimit = Math.max(Math.abs(maxVal), Math.abs(minVal)) * 1.2
      if (absLimit === 0) absLimit = 1 // Y轴兜底防塌陷

      myChart.setOption({
        xAxis: { data: times },
        yAxis: { min: -absLimit, max: absLimit },
        series: [{ data: values }]
      })
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

<style scoped>
.no-data-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
  background-color: rgba(255, 255, 255, 0.85); /* 半透明白底 */
  z-index: 10;
}

.no-data-text {
  color: #888;
  font-size: 15px;
  background: #f4f5f7;
  padding: 12px 24px;
  border-radius: 6px;
  border: 1px solid #eaeaea;
}
</style>