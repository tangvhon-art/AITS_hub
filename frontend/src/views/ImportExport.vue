<template>
  <div class="import-export-page">
    <div class="page-header">
      <h2>数据导入导出</h2>
    </div>

    <a-row :gutter="16">
      <a-col :span="12">
        <a-card title="用例导出">
          <p style="color: #666; margin-bottom: 16px">
            将项目中的所有测试用例导出为 Excel 或 XMind 文件，包含用例标题、模块、优先级、步骤、预期结果等字段。
          </p>
          <a-space>
            <a-button type="primary" @click="handleExport" :loading="exporting">
              <DownloadOutlined /> 导出 Excel
            </a-button>
            <a-button @click="handleExportXmind" :loading="exportingXmind">
              <DownloadOutlined /> 导出 XMind
            </a-button>
          </a-space>
          <a-divider />
          <h4>导出说明</h4>
          <a-list size="small">
            <a-list-item>Excel：用例标题、所属模块、优先级、前置条件、测试步骤、预期结果等</a-list-item>
            <a-list-item>XMind：所属模块 → 用例标题 → 前置条件 → 测试步骤（自然语言）</a-list-item>
          </a-list>
        </a-card>
      </a-col>

      <a-col :span="12">
        <a-card title="用例导入">
          <p style="color: #666; margin-bottom: 16px">
            从 Excel 文件批量导入测试用例，支持标准模板格式。
          </p>
          <a-space direction="vertical" style="width: 100%">
            <a-button @click="handleDownloadTemplate">
              <FileTextOutlined /> 下载导入模板
            </a-button>
            <a-upload
              :before-upload="handleBeforeUpload"
              :show-upload-list="false"
              accept=".xlsx,.xls"
            >
              <a-button type="primary" :loading="importing">
                <UploadOutlined /> 选择 Excel 文件导入
              </a-button>
            </a-upload>
          </a-space>

          <a-alert
            v-if="importResult"
            :type="importResult.failed > 0 ? 'warning' : 'success'"
            :message="`导入完成：成功 ${importResult.imported} 条，失败 ${importResult.failed} 条`"
            style="margin-top: 16px"
            show-icon
          />

          <a-divider />
          <h4>导入说明</h4>
          <a-list size="small">
            <a-list-item>必须包含「用例标题」列</a-list-item>
            <a-list-item>测试步骤每行一个，可带序号</a-list-item>
            <a-list-item>优先级：P0/P1/P2/P3，默认 P2</a-list-item>
            <a-list-item>状态：draft/active/archived，默认 active</a-list-item>
          </a-list>
        </a-card>
      </a-col>
    </a-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { message } from 'ant-design-vue'
import {
  DownloadOutlined, UploadOutlined, FileTextOutlined
} from '@ant-design/icons-vue'
import { exportCases, exportCasesXmind, importCases, downloadTemplate } from '@/api/importExport'
import { useProjectStore } from '@/stores/project'

const route = useRoute()
const projectId = Number(route.params.id)
const projectStore = useProjectStore()

onMounted(() => {
  projectStore.ensureProjects()
})

const exporting = ref(false)
const exportingXmind = ref(false)
const importing = ref(false)
const importResult = ref<{ imported: number; failed: number; errors?: string[] } | null>(null)

function downloadBlob(blob: Blob, filename: string) {
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  window.URL.revokeObjectURL(url)
}

async function handleExport() {
  exporting.value = true
  try {
    const blob = await exportCases(projectId) as any
    downloadBlob(blob, `测试用例-${projectStore.getProjectName(projectId)}.xlsx`)
    message.success('导出成功')
  } catch (e: any) {
    message.error(e.response?.data?.detail || '导出失败')
  } finally {
    exporting.value = false
  }
}

async function handleExportXmind() {
  exportingXmind.value = true
  try {
    const blob = await exportCasesXmind(projectId) as any
    downloadBlob(blob, `测试用例-${projectStore.getProjectName(projectId)}.xmind`)
    message.success('导出成功')
  } catch (e: any) {
    message.error(e.response?.data?.detail || '导出失败')
  } finally {
    exportingXmind.value = false
  }
}

async function handleDownloadTemplate() {
  try {
    const blob = await downloadTemplate(projectId) as any
    downloadBlob(blob, 'test_case_template.xlsx')
    message.success('模板下载成功')
  } catch (e: any) {
    message.error(e.response?.data?.detail || '下载失败')
  }
}

async function handleBeforeUpload(file: File) {
  if (!file.name.endsWith('.xlsx') && !file.name.endsWith('.xls')) {
    message.error('仅支持 Excel 文件格式')
    return false
  }

  importing.value = true
  importResult.value = null
  try {
    const result: any = await importCases(projectId, file)
    importResult.value = result
    if (result.failed > 0) {
      message.warning(`导入完成：成功 ${result.imported} 条，失败 ${result.failed} 条`)
    } else {
      message.success(`导入成功：${result.imported} 条用例`)
    }
  } catch (e: any) {
    message.error(e.response?.data?.detail || '导入失败')
  } finally {
    importing.value = false
  }
  return false
}
</script>

<style scoped>
.import-export-page { padding: 20px; }
.page-header { margin-bottom: 16px; }
.page-header h2 { margin: 0; font-size: 20px; }
</style>
