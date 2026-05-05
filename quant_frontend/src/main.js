import { createApp } from 'vue'
import { createPinia } from 'pinia' // 必须引入这个
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import 'element-plus/dist/index.css'
import App from './App.vue'
import router from './router'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'

const app = createApp(App)

// 注册所有图标
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

app.use(createPinia()) // 🟢 这一行是关键，必须要有！
app.use(router)
app.use(ElementPlus, {
  locale: zhCn
})

app.mount('#app')
