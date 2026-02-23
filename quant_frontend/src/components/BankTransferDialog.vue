<template>
  <el-dialog
    v-model="visibleModel"
    title="银证转账"
    width="400px"
    destroy-on-close
  >
    <el-form label-position="top">
      <el-form-item label="操作类型">
        <el-radio-group v-model="transferType">
          <el-radio-button value="deposit">转入 (充值)</el-radio-button>
          <el-radio-button value="withdraw">转出 (提现)</el-radio-button>
        </el-radio-group>
      </el-form-item>

      <el-form-item :label="transferType === 'deposit' ? '转入金额' : '转出金额'">
        <el-input v-model="transferAmount" type="number" placeholder="请输入金额">
          <template #prefix>¥</template>
        </el-input>
        <div class="balance-hint" v-if="transferType === 'withdraw'">
          可转出余额: ¥ {{ formatNumber(userData.balance) }}
        </div>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="visibleModel = false">取消</el-button>
      <el-button type="primary" @click="handleTransfer" :loading="loading">
        确认{{ transferType === 'deposit' ? '转入' : '转出' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'

const props = defineProps({
  visible: Boolean,
  userData: {
    type: Object,
    default: () => ({ balance: 0 })
  }
})

const emit = defineEmits(['update:visible', 'success'])

const visibleModel = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val)
})

const transferType = ref('deposit')
const transferAmount = ref('')
const loading = ref(false)

// 每次打开弹窗重置数据
watch(() => props.visible, (val) => {
  if (val) {
    transferType.value = 'deposit'
    transferAmount.value = ''
  }
})

const formatNumber = (num) => {
  return Number(num || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

const handleTransfer = async () => {
  const amount = parseFloat(transferAmount.value)
  if (!amount || amount <= 0) return ElMessage.warning('请输入有效的金额')

  let finalAmount = transferType.value === 'withdraw' ? -amount : amount
  if (transferType.value === 'withdraw' && amount > props.userData.balance) {
    return ElMessage.error('可用余额不足')
  }

  loading.value = true
  try {
    const api = axios.create({
      baseURL: 'http://127.0.0.1:8000/',
      headers: { 'Authorization': `Token ${localStorage.getItem('token')}` }
    })

    const res = await api.post('trade/api/transfer/', { amount: finalAmount })
    if (res.data.code === 200) {
      ElMessage.success('操作成功')
      visibleModel.value = false
      emit('success') // 通知父组件刷新数据
    } else {
      ElMessage.error(res.data.msg || '操作失败')
    }
  } catch (e) {
    ElMessage.error('请求失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.balance-hint { font-size: 12px; color: #909399; margin-top: 5px; }
</style>