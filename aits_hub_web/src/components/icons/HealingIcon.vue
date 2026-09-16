<template>
  <svg viewBox="0 0 1024 1024" xmlns="http://www.w3.org/2000/svg" :width="size" :height="size" fill="currentColor" aria-hidden="true">
    <!-- 盾牌外框 -->
    <path d="M512 64L128 192v256c0 256 192 448 384 512 192-64 384-256 384-512V192L512 64z" fill="none" stroke="currentColor" stroke-width="56" stroke-linejoin="round"/>
    <!-- 心跳线 -->
    <polyline points="288,512 400,512 448,416 512,608 576,448 624,512 736,512"
              fill="none" stroke="currentColor" stroke-width="48" stroke-linecap="round" stroke-linejoin="round"/>
  </svg>
</template>

<script setup lang="ts">
withDefaults(defineProps<{ size?: number | string }>(), { size: '1em' })
</script>
