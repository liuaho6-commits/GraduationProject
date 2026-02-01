<template>
  <div class="login-container">
    <div class="login-box">
      <div class="title">Quant Pro 量化交易系统</div>
      <el-form :model="form" :rules="rules" ref="loginFormRef" size="large">
        <el-form-item prop="username">
          <el-input v-model="form.username" placeholder="用户名" :prefix-icon="User" />
        </el-form-item>
        <el-form-item prop="password">
          <el-input v-model="form.password" type="password" placeholder="密码" :prefix-icon="Lock" show-password />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" class="w-100" @click="handleLogin" :loading="loading">登录</el-button>
        </el-form-item>
      </el-form>

      <div class="links">
        <el-link type="primary" @click="$router.push('/register')">没有账号？去注册</el-link>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { User, Lock } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'

const router = useRouter()
const loginFormRef = ref(null)
const loading = ref(false)

const form = reactive({
  username: '',
  password: ''
})

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
}

const handleLogin = async () => {
  if (!loginFormRef.value) return

  await loginFormRef.value.validate(async (valid) => {
    if (valid) {
      loading.value = true
      try {
        const res = await axios.post('http://127.0.0.1:8000/api/users/login/', form)

        // 🟢 核心修复：根据后端实际返回结构解析数据
        // 后端返回结构: { code: 200, data: { token: 'xxx', username: 'xxx' } }
        if (res.data.code === 200) {
          const responseData = res.data.data // 获取嵌套的 data 对象

          if (responseData && responseData.token) {
              localStorage.setItem('token', responseData.token)

              // 构建用户信息对象
              const userInfo = {
                  username: responseData.username || form.username
              }
              localStorage.setItem('user', JSON.stringify(userInfo)) // 注意：MainLayout里读取的是 'user' 不是 'userInfo'

              ElMessage.success('登录成功')
              router.push('/dashboard')
          } else {
              ElMessage.error('登录异常：未获取到令牌')
          }
        } else {
          ElMessage.error(res.data.msg || '登录失败')
        }
      } catch (err) {
        console.error(err)
        ElMessage.error('登录请求失败，请检查网络或账号')
      } finally {
        loading.value = false
      }
    }
  })
}
</script>

<style scoped>
.login-container {
  height: 100vh;
  display: flex;
  justify-content: center;
  align-items: center;
  background-color: #2d3a4b;
}
.login-box {
  width: 400px;
  padding: 40px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
}
.title {
  text-align: center;
  font-size: 24px;
  font-weight: bold;
  margin-bottom: 30px;
  color: #333;
}
.w-100 { width: 100%; }
.links {
  display: flex;
  justify-content: center;
  margin-top: 15px;
}
</style>