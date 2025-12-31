<template>
  <el-dialog
    v-model="visibleModel"
    :title="direction === 'buy' ? '买入委托' : '卖出委托'"
    width="400px"
    destroy-on-close
  >
    <el-form :model="form" label-width="80px">
      <el-form-item label="股票代码">
        <el-input v-model="form.code" disabled />
      </el-form-item>

      <el-form-item label="委托价格">
        <el-input-number
            v-model="form.price"
            :precision="2"
            :step="0.01"
            style="width: 100%"
        />
        <div class="price-tip">
             (自动填入: {{ price }})
        </div>
      </el-form-item>

      <el-form-item label="委托数量">
        <el-input-number
            v-model="form.volume"
            :step="100"
            :min="100"
            step-strictly
            style="width: 100%"
        />
        <div class="volume-tip">必须是100的倍数</div>
      </el-form-item>

      <el-form-item label="预估金额">
        <span class="total-amount">¥ {{ (form.price * form.volume).toFixed(2) }}</span>
      </el-form-item>
    </el-form>

    <template #footer>
      <span class="dialog-footer">
        <el-button @click="visibleModel = false">取消</el-button>
        <el-button
            type="primary"
            :loading="loading"
            @click="submitOrder"
            :class="direction === 'buy' ? 'buy-btn' : 'sell-btn'"
        >
          {{ direction === 'buy' ? '确认买入' : '确认卖出' }}
        </el-button>
      </span>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'

const props = defineProps({
  visible: Boolean,
  direction: String,
  stockCode: String,
  price: Number,
  preClose: Number
})

const emit = defineEmits(['update:visible', 'success'])

const visibleModel = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val)
})

const form = ref({
  code: '',
  price: 0,
  volume: 100
})

const loading = ref(false)

watch(() => props.visible, (val) => {
    if (val) {
        form.value.code = props.stockCode
        // 初始值由父组件传入
        form.value.price = props.price
        form.value.volume = 100
    }
})

const submitOrder = async () => {
    if (form.value.price <= 0) return ElMessage.warning('价格无效')
    if (form.value.volume <= 0) return ElMessage.warning('数量无效')

    loading.value = true
    try {
        const api = axios.create({
            baseURL: 'http://127.0.0.1:8000/',
            headers: { 'Authorization': `Token ${localStorage.getItem('token')}` }
        })

        // 🟢 修正接口地址，匹配后端 api/trade/place_order/
        const res = await api.post('api/trade/place_order/', {
            code: form.value.code, // 后端用的是 'code' 不是 'stock_code'
            direction: props.direction,
            price: form.value.price,
            volume: form.value.volume
        })

        if (res.data.code === 200) {
            ElMessage.success('交易成功')
            visibleModel.value = false
            emit('success')
        } else {
            // 🟢 显示具体的错误原因 (如余额不足)
            ElMessage.error(res.data.msg || '交易失败')
        }
    } catch (err) {
        if (err.response && err.response.data && err.response.data.msg) {
             ElMessage.error(err.response.data.msg)
        } else {
             ElMessage.error('网络请求失败')
        }
    } finally {
        loading.value = false
    }
}
</script>

<style scoped>
.price-tip, .volume-tip { font-size: 12px; color: #909399; margin-top: 4px; line-height: 1.2; }
.total-amount { font-size: 18px; font-weight: bold; color: #f56c6c; }
.buy-btn { background-color: #f56c6c; border-color: #f56c6c; }
.buy-btn:hover { background-color: #f78989; border-color: #f78989; }
.sell-btn { background-color: #409eff; border-color: #409eff; }
</style>