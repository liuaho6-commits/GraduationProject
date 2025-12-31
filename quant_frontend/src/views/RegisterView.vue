<template>
  <div class="register-container">
    <div class="register-box">
      <div class="title">Quant Pro 注册</div>
      <el-form :model="form" :rules="rules" ref="registerFormRef" size="large">

        <el-form-item prop="username">
          <el-input v-model="form.username" placeholder="请输入用户名" :prefix-icon="User" />
        </el-form-item>

        <el-form-item prop="phone">
          <el-input v-model="form.phone" placeholder="请输入手机号" :prefix-icon="Iphone" maxlength="11" />
        </el-form-item>

        <el-form-item prop="password">
          <el-input v-model="form.password" type="password" placeholder="请输入密码 (至少6位)" :prefix-icon="Lock" show-password />
        </el-form-item>

        <el-form-item prop="password_confirm">
          <el-input v-model="form.password_confirm" type="password" placeholder="请确认密码" :prefix-icon="Lock" show-password />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" class="w-100" @click="handleRegister" :loading="loading">立即注册</el-button>
        </el-form-item>
      </el-form>
      <div class="links">
        <el-link type="primary" @click="$router.push('/login')">已有账号？去登录</el-link>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
// 🟢 记得引入 Iphone 图标
import { User, Lock, Iphone } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'

const router = useRouter()
const registerFormRef = ref(null)
const loading = ref(false)

const form = reactive({
  username: '',
  phone: '', // 🟢
  password: '',
  password_confirm: ''
})

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  // 🟢 手机号验证
  phone: [
    { required: true, message: '请输入手机号', trigger: 'blur' },
    { min: 11, max: 11, message: '手机号格式不正确', trigger: 'blur' },
    { pattern: /^\d+$/, message: '只能输入数字', trigger: 'blur' }
  ],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }, { min: 6, message: '密码长度至少6位', trigger: 'blur' }],
  password_confirm: [{ required: true, message: '请确认密码', trigger: 'blur' }]
}

const handleRegister = async () => {
  if (!registerFormRef.value) return

  await registerFormRef.value.validate(async (valid) => {
    if (valid) {
      if (form.password !== form.password_confirm) {
        ElMessage.error('两次输入的密码不一致')
        return
      }

      loading.value = true
      try {
        const res = await axios.post('http://127.0.0.1:8000/api/users/register/', {
          username: form.username,
          phone: form.phone, // 🟢 传给后端
          password: form.password,
          password_confirm: form.password_confirm
        })

        if (res.data.code === 200) {
          ElMessage.success('注册成功，自动登录')
          localStorage.setItem('token', res.data.token)
          localStorage.setItem('userInfo', JSON.stringify(res.data.userInfo))
          router.push('/dashboard')
        } else {
          ElMessage.error(res.data.msg)
        }
      } catch (err) {
        if (err.response && err.response.data) {
           // 处理后端返回的字段级错误 (比如 {phone: ['手机号必须是11位']})
           const errors = err.response.data.errors
           if (errors) {
             const firstKey = Object.keys(errors)[0]
             ElMessage.error(errors[firstKey][0])
           } else {
             ElMessage.error(err.response.data.msg || '注册失败')
           }
        } else {
           ElMessage.error('网络错误')
        }
      } finally {
        loading.value = false
      }
    }
  })
}
</script>

<style scoped>
.register-container {
  height: 100vh;
  display: flex;
  justify-content: center;
  align-items: center;
  background-color: #2d3a4b;
}
.register-box {
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
  justify-content: flex-end;
  margin-top: 10px;
}
</style>