<template>
  <a-tag :color="resolvedColor">{{ resolvedText }}</a-tag>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { colorOf, labelOf } from '@/constants/enums'

const props = withDefaults(defineProps<{
  value: string
  colorMap?: Record<string, string>
  textMap?: Record<string, string>
  text?: string
}>(), {
  colorMap: () => ({}),
  textMap: () => ({}),
  text: '',
})

const resolvedColor = computed(() => colorOf(props.colorMap, props.value))
const resolvedText = computed(() => props.text || labelOf(props.textMap, props.value))
</script>
