import { createApp } from 'vue'
import { createPinia } from 'pinia'
import Antd from 'ant-design-vue'
import 'ant-design-vue/dist/reset.css'
import App from './App.vue'
import router from './router'
import './assets/main.css'
import { formatDateTime, formatDate, formatRelativeTime } from './utils/date'

const app = createApp(App)

// 注册全局时间格式化方法
app.config.globalProperties.$formatDateTime = formatDateTime
app.config.globalProperties.$formatDate = formatDate
app.config.globalProperties.$formatRelativeTime = formatRelativeTime

app.use(createPinia())
app.use(router)
app.use(Antd)

app.mount('#app')
