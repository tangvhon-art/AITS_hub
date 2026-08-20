<template>
  <svg viewBox="0 0 1024 1024" xmlns="http://www.w3.org/2000/svg" :width="size" :height="size" fill="currentColor" aria-hidden="true">
    <!-- 中心节点 -->
    <circle cx="512" cy="512" r="96" fill="currentColor"/>
    <!-- 周围节点 -->
    <circle cx="512" cy="160" r="64" fill="none" stroke="currentColor" stroke-width="48"/>
    <circle cx="832" cy="352" r="64" fill="none" stroke="currentColor" stroke-width="48"/>
    <circle cx="832" cy="672" r="64" fill="none" stroke="currentColor" stroke-width="48"/>
    <circle cx="512" cy="864" r="64" fill="none" stroke="currentColor" stroke-width="48"/>
    <circle cx="192" cy="672" r="64" fill="none" stroke="currentColor" stroke-width="48"/>
    <circle cx="192" cy="352" r="64" fill="none" stroke="currentColor" stroke-width="48"/>
    <!-- 连接线 -->
    <g stroke="currentColor" stroke-width="32" stroke-linecap="round">
      <line x1="512" y1="224" x2="512" y2="416"/>
      <line x1="778" y1="384" x2="592" y2="464"/>
      <line x1="778" y1="640" x2="592" y2="560"/>
      <line x1="512" y1="800" x2="512" y2="608"/>
      <line x1="246" y1="640" x2="432" y2="560"/>
      <line x1="246" y1="384" x2="432" y2="464"/>
    </g>
  </svg>
</template>

<script setup lang="ts">
withDefaults(defineProps<{ size?: number | string }>(), { size: '1em' })
</script>
