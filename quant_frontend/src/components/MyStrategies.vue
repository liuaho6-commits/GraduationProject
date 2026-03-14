<template>
  <el-card class="strategy-card">
    <template #header>
      <div class="card-header">
        <span>我的量化策略 (实盘运行)</span>
        <el-button type="primary" size="small" @click="openDialog()">新建实盘策略</el-button>
      </div>
    </template>

    <el-table :data="strategies" v-loading="loading" style="width: 100%" border stripe>
      <el-table-column prop="name" label="策略名称" width="200" align="center" />
      <el-table-column prop="stock_pool" label="交易股票池" align="center" show-overflow-tooltip />
      <el-table-column label="多因子参数" width="220" align="center">
        <template #default="scope">
          <div style="font-size: 12px; line-height: 1.5; text-align: left; display: inline-block;">
            动量权重: {{ parseConfig(scope.row.code).weight_mom }}<br/>
            偏离权重: {{ parseConfig(scope.row.code).weight_bias }}<br/>
            选股Top: {{ parseConfig(scope.row.code).top_n }}
          </div>
        </template>
      </el-table-column>
      <el-table-column label="运行状态" width="120" align="center">
        <template #default="scope">
          <el-switch
            v-model="scope.row.status"
            active-value="active"
            inactive-value="stopped"
            active-text="运行"
            inactive-text="停止"
            @change="toggleStatus(scope.row)"
          />
        </template>
      </el-table-column>
      <el-table-column label="操作" width="150" align="center">
        <template #default="scope">
          <el-button size="small" @click="openDialog(scope.row)">参数设置</el-button>
          <el-popconfirm title="确定删除这个策略吗？" @confirm="deleteStrategy(scope.row.id)">
            <template #reference>
              <el-button size="small" type="danger" style="margin-left: 5px;">删除</el-button>
            </template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog
      v-model="dialogVisible"
      :title="currentStrategy.id ? '调整多因子参数' : '新建多因子策略'"
      width="600px"
      destroy-on-close
    >
      <el-form label-width="120px" :model="currentStrategy">
        <el-form-item label="策略名称">
          <el-input v-model="currentStrategy.name" placeholder="例如: 动量轮动实盘策略" />
        </el-form-item>
        <el-form-item label="股票池">
          <el-input v-model="currentStrategy.stock_pool" placeholder="英文逗号分隔，例如: sz.300394, sh.600000" type="textarea" :rows="3"/>
        </el-form-item>

        <el-divider>多因子权重配置 (矩阵 Z-Score)</el-divider>

        <el-form-item label="动量因子权重">
          <el-slider v-model="currentStrategy.weight_mom" :min="-1" :max="1" :step="0.1" show-input />
        </el-form-item>
        <el-form-item label="均线偏离权重">
          <el-slider v-model="currentStrategy.weight_bias" :min="-1" :max="1" :step="0.1" show-input />
        </el-form-item>
        <el-form-item label="每日选股数 (Top N)">
          <el-input-number v-model="currentStrategy.top_n" :min="1" :max="20" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveStrategy" :loading="saving">保存并应用</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'

const strategies = ref([])
const loading = ref(false)
const saving = ref(false)
const dialogVisible = ref(false)
const currentStrategy = ref({
  id: null, name: '', stock_pool: '',
  weight_mom: 0.5, weight_bias: -0.5, top_n: 2
})

const getApi = () => {
  return axios.create({
    baseURL: 'http://127.0.0.1:8000/',
    headers: { 'Authorization': 'Token ' + localStorage.getItem('token') }
  })
}

const parseConfig = (codeStr) => {
  try {
    return JSON.parse(codeStr)
  } catch (e) {
    return { weight_mom: 0, weight_bias: 0, top_n: 0 }
  }
}

// 获取策略列表
const fetchStrategies = async () => {
  loading.value = true
  try {
    const res = await getApi().get('api/trade/strategy/')
    if (res.data.code === 200) {
      strategies.value = res.data.data
    }
  } catch (e) {
    console.error('获取策略失败', e)
  } finally {
    loading.value = false
  }
}

// 切换策略状态
const toggleStatus = async (row) => {
  try {
    const res = await getApi().post('api/trade/strategy/', {
      id: row.id,
      status: row.status
    })
    if (res.data.code === 200) {
      ElMessage.success(row.status === 'active' ? '引擎已就绪！将在开/尾盘执行轮动' : '策略已停止')
    } else {
      throw new Error(res.data.msg)
    }
  } catch (e) {
    ElMessage.error('状态切换失败')
    row.status = row.status === 'active' ? 'stopped' : 'active' // 状态回滚
  }
}

// 打开弹窗并解析 JSON
const openDialog = (row = null) => {
  if (row) {
    const config = parseConfig(row.code)
    currentStrategy.value = {
      id: row.id,
      name: row.name,
      stock_pool: row.stock_pool,
      weight_mom: config.weight_mom || 0.5,
      weight_bias: config.weight_bias || -0.5,
      top_n: config.top_n || 2
    }
  } else {
    currentStrategy.value = {
      id: null, name: '新建多因子策略', stock_pool: '',
      weight_mom: 0.5, weight_bias: -0.5, top_n: 2
    }
  }
  dialogVisible.value = true
}

// 保存策略 (打包成 JSON 存入 code 字段)
const saveStrategy = async () => {
  if (!currentStrategy.value.name) return ElMessage.warning('请填写策略名称')
  saving.value = true

  const payload = {
    name: currentStrategy.value.name,
    stock_pool: currentStrategy.value.stock_pool,
    code: JSON.stringify({
      weight_mom: currentStrategy.value.weight_mom,
      weight_bias: currentStrategy.value.weight_bias,
      top_n: currentStrategy.value.top_n
    })
  }
  if (currentStrategy.value.id) {
    payload.id = currentStrategy.value.id
  }

  try {
    const res = await getApi().post('api/trade/strategy/', payload)
    if (res.data.code === 200) {
      ElMessage.success('保存成功')
      dialogVisible.value = false
      fetchStrategies()
    } else {
      ElMessage.error(res.data.msg || '保存失败')
    }
  } catch (e) {
    ElMessage.error('保存请求失败')
  } finally {
    saving.value = false
  }
}

// 删除策略
const deleteStrategy = async (id) => {
  try {
    const res = await getApi().delete('api/trade/strategy/', { data: { id } })
    if (res.data.code === 200) {
      ElMessage.success('删除成功')
      fetchStrategies()
    }
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

onMounted(() => {
  fetchStrategies()
})
</script>

<style scoped>
.strategy-card { margin-top: 20px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
</style>