import { createApp } from 'vue'
import { createPinia } from 'pinia'
import Antd from 'ant-design-vue'
import zhCN from 'ant-design-vue/es/locale/zh_CN'
import dayjs from 'dayjs'
import 'dayjs/locale/zh-cn'
import 'ant-design-vue/dist/reset.css'
import App from './App.vue'
import router from './router'
import './assets/main.css'
import { formatDateTime, formatDate, formatRelativeTime } from './utils/date'

// dayjs 中文
dayjs.locale('zh-cn')

const app = createApp(App)

// 全局错误处理
app.config.errorHandler = (err, _instance, info) => {
  console.error('全局错误:', err, '\n组件信息:', info)
}

// 注册全局时间格式化方法
app.config.globalProperties.$formatDateTime = formatDateTime
app.config.globalProperties.$formatDate = formatDate
app.config.globalProperties.$formatRelativeTime = formatRelativeTime

// 全局注入中文语言包
app.config.globalProperties.$antLocale = zhCN

app.use(createPinia())
app.use(router)
app.use(Antd)

app.mount('#app')
