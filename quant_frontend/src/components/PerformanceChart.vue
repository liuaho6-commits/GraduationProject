<template>
  <div class="chart-container">
    <div class="chart-header">
      <h3 class="title">资产收益分析</h3>
      <el-radio-group v-model="currentTab" size="small">
        <el-radio-button label="daily">日线表现</el-radio-button>
        <el-radio-button label="intraday">当日分时</el-radio-button>
      </el-radio-group>
    </div>

    <keep-alive>
      <component :is="currentChartComponent" />
    </keep-alive>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import DailyChart from './DailyPerformanceChart.vue'
import IntradayChart from './IntradayPerformanceChart.vue'

const currentTab = ref('daily')

// 根据 tab 决定渲染哪个组件
const currentChartComponent = computed(() => {
  return currentTab.value === 'daily' ? DailyChart : IntradayChart
})
</script>

<style scoped>
.chart-container {
  background: #fff;
  padding: 20px;
  border-radius: 8px;
  /* 稍微加点阴影让它好看点 */
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.05);
}
.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
.title {
  font-size: 16px;
  font-weight: bold;
  color: #333;
  border-left: 4px solid #E55555;
  padding-left: 10px;
}
</style>