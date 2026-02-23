<template>
  <div class="header-row">
    <div class="header-left">
      <el-tabs
        :model-value="activeTab"
        @update:model-value="$emit('update:activeTab', $event)"
        @tab-change="$emit('tab-change', $event)"
        class="no-border-tabs"
      >
        <el-tab-pane label="全市场行情" name="all"></el-tab-pane>
        <el-tab-pane label="我的自选股" name="favorites"></el-tab-pane>
      </el-tabs>
    </div>

    <div class="header-right">
      <transition name="el-fade-in">
        <span v-if="marketTime" class="market-time">
          <el-icon><Clock /></el-icon> {{ marketTime }}
        </span>
      </transition>
      <el-divider direction="vertical" />
      <el-button
        type="primary"
        :icon="Refresh"
        circle
        plain
        @click="$emit('refresh')"
        title="手动刷新"
      />
    </div>
  </div>
</template>

<script setup>
import { Clock, Refresh } from '@element-plus/icons-vue'

defineProps({
  activeTab: { type: String, required: true },
  marketTime: { type: String, default: '' }
})

defineEmits(['update:activeTab', 'tab-change', 'refresh'])
</script>

<style scoped>
.header-row { display: flex; justify-content: space-between; align-items: center; padding-bottom: 2px; }
.header-right { display: flex; align-items: center; gap: 12px; }
.market-time {
    font-size: 13px;
    color: #64748b;
    font-family: 'Roboto Mono', monospace;
    display: flex;
    align-items: center;
    gap: 6px;
    background: #f1f5f9;
    padding: 4px 10px;
    border-radius: 6px;
}
</style>