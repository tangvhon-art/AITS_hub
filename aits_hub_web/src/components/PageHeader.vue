<template>
  <div class="page-header">
    <h2 class="page-title">{{ title }}</h2>
    <div class="header-extra">
      <slot name="extra" />
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  title: string
}>()
</script>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.page-title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
}

.header-extra {
  display: flex;
  gap: 8px;
  align-items: center;
}
</style>
