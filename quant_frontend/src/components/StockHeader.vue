<template>
  <el-page-header @back="$emit('back')" class="custom-header">
    <template #content>
      <div class="header-left">
        <span class="stock-title">{{ stockName }} <span class="stock-code">({{ stockCode }})</span></span>
        <transition name="el-fade-in">
          <el-tag v-if="viewMode === 'min'" type="success" effect="light" round size="small" class="live-tag">
            <span class="dot"></span> 盘中直播
          </el-tag>
        </transition>
      </div>
    </template>

    <template #extra>
      <div class="header-right">
        <div class="time-display" v-if="systemTime">
          <el-icon><Clock /></el-icon> {{ systemTime }}
        </div>

        <el-radio-group :model-value="viewMode" size="small" @change="$emit('update:viewMode', $event)">
          <el-radio-button value="min">分时</el-radio-button>
          <el-radio-button value="daily">日K</el-radio-button>
        </el-radio-group>
      </div>
    </template>
  </el-page-header>
</template>

<script setup>
import { Clock } from '@element-plus/icons-vue'

defineProps({
  stockName: { type: String, default: '--' },
  stockCode: { type: String, default: '' },
  viewMode: { type: String, default: 'min' },
  systemTime: { type: String, default: '' }
})

defineEmits(['back', 'update:viewMode'])
</script>

<style scoped>
.custom-header { background: #fff; padding: 12px 20px; border-radius: 8px; margin-bottom: 20px; }
.header-left { display: flex; align-items: center; gap: 12px; }
.stock-title { font-size: 22px; font-weight: 700; color: #1e293b; }
.stock-code { font-size: 14px; color: #64748b; font-weight: normal; margin-left: 6px; }
.header-right { display: flex; align-items: center; }
.time-display { font-family: 'Roboto Mono', monospace; font-size: 14px; color: #64748b; margin-right: 15px; display: flex; align-items: center; gap: 5px; }
.live-tag { display: flex; align-items: center; gap: 4px; }
.dot { width: 6px; height: 6px; background: #67c23a; border-radius: 50%; display: inline-block; animation: pulse 1.5s infinite; }

@keyframes pulse {
  0% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(1.2); }
  100% { opacity: 1; transform: scale(1); }
}
</style>