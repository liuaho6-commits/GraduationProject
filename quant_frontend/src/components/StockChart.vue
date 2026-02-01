<template>
  <div className="stock-chart-wrapper">
    <StockMinuteChart
        v-if="freq === 'min' || freq === '5min'"
        :key="freq"
        :data="data"
    />

    <StockDailyChart
        v-else-if="freq === 'daily'"
        :data="data"
    />
  </div>
</template>

<script setup>
import StockMinuteChart from './StockMinuteChart.vue'
import StockDailyChart from './StockDailyChart.vue'

defineProps({
  data: {type: Array, default: () => []},
  freq: {type: String, default: 'min'}
})
</script>

<style scoped>
.stock-chart-wrapper {
  width: 100%;
  height: 100%;
  position: relative;
}
</style>