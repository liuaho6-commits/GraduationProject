import { createRouter, createWebHistory } from 'vue-router'
import LoginView from '../views/LoginView.vue'
import RegisterView from '../views/RegisterView.vue'
import DashboardView from '../views/DashboardView.vue'
import MarketView from '../views/MarketView.vue'
import StockDetailView from '../views/StockDetailView.vue' // 🟢 引入详情页
import MainLayout from '../layout/MainLayout.vue'
import BacktestView from '../views/BacktestView.vue' // 🟢 1. 引入新页面
const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: LoginView
    },
    {
      path: '/register',
      name: 'register',
      component: RegisterView
    },
    {
      path: '/',
      component: MainLayout,
      redirect: '/dashboard',
      children: [
        {
          path: 'dashboard',
          name: 'dashboard',
          component: DashboardView
        },
        {
          path: 'market',
          name: 'market',
          component: MarketView
        },
        // 🟢 新增路由：K线详情页
        {
          path: 'stock/:code',
          name: 'stock-detail',
          component: StockDetailView
        },
        {
          path: 'backtest',
          name: 'backtest',
          component: BacktestView
        }
      ]
    }
  ]
})

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')
  if ((to.name === 'login' || to.name === 'register') && !token) {
    next()
  } else if (!token && to.name !== 'login' && to.name !== 'register') {
    next({ name: 'login' })
  } else {
    next()
  }
})

export default router