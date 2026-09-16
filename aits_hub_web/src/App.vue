<template>
  <a-config-provider :locale="zhCN">
    <div class="app-content">
      <router-view />
    </div>
  </a-config-provider>
</template>

<script setup lang="ts">
import zhCN from 'ant-design-vue/es/locale/zh_CN'
</script>

<style>
/* 全局页面内容容器：统一左右边距，保证所有页面内容不与视口贴边 */
.app-content {
  padding: 20px 24px;
  min-height: 100vh;
}

/* 沉浸式页面（登录页）不套用全局边距 */
.app-content:has(.login-container) {
  padding: 0;
}
</style>
