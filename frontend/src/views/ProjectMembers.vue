<template>
  <div class="project-members">
    <a-card title="成员管理" :bordered="false">
      <template #extra>
        <a-button type="primary" @click="showAddModal" v-if="canManage">
          <PlusOutlined />
          添加成员
        </a-button>
      </template>

      <a-table
        :columns="columns"
        :data-source="members"
        :loading="loading"
        row-key="id"
        :pagination="false"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'username'">
            <a-avatar size="small" style="background-color: #1677ff; margin-right: 8px">
              {{ record.username.charAt(0).toUpperCase() }}
            </a-avatar>
            {{ record.username }}
            <span v-if="record.full_name" style="color: #999; margin-left: 4px">({{ record.full_name }})</span>
          </template>
          <template v-else-if="column.key === 'role'">
            <a-tag :color="roleColors[record.role] || 'default'">
              {{ roleLabels[record.role] || record.role }}
            </a-tag>
          </template>
          <template v-else-if="column.key === 'action'">
            <a-space v-if="canManage && record.role !== 'owner'">
              <a-select
                :value="record.role"
                size="small"
                style="width: 110px"
                @change="(val: string) => handleRoleChange(record, val)"
              >
                <a-select-option value="admin">管理员</a-select-option>
                <a-select-option value="developer">开发者</a-select-option>
                <a-select-option value="tester">测试</a-select-option>
              </a-select>
              <a-popconfirm
                title="确定要移除该成员吗？"
                @confirm="handleRemove(record)"
              >
                <a-button type="link" size="small" danger>移除</a-button>
              </a-popconfirm>
            </a-space>
            <span v-else-if="record.role === 'owner'" style="color: #999">—</span>
          </template>
        </template>
      </a-table>
    </a-card>

    <a-modal
      v-model:open="addModalVisible"
      title="添加成员"
      @ok="handleAdd"
      :confirm-loading="addLoading"
      width="520px"
    >
      <div style="margin-bottom: 16px">
        <label style="display: block; margin-bottom: 8px; font-weight: 500">搜索用户</label>
        <a-input-search
          v-model:value="searchKeyword"
          placeholder="输入用户名或邮箱搜索"
          @search="handleSearch"
          :loading="searchLoading"
        />
      </div>
      <div v-if="searchResults.length > 0" style="margin-bottom: 16px">
        <label style="display: block; margin-bottom: 8px; font-weight: 500">选择用户</label>
        <a-list
          :data-source="searchResults"
          size="small"
          bordered
          style="max-height: 200px; overflow-y: auto"
        >
          <template #renderItem="{ item }">
            <a-list-item
              @click="selectedUser = item"
              :class="{ 'selected-user': selectedUser?.id === item.id }"
              style="cursor: pointer; padding: 8px 12px"
            >
              <a-space>
                <a-avatar size="small" style="background-color: #1677ff">
                  {{ item.username.charAt(0).toUpperCase() }}
                </a-avatar>
                <span>{{ item.username }}</span>
                <span style="color: #999">{{ item.email }}</span>
              </a-space>
              <CheckOutlined v-if="selectedUser?.id === item.id" style="color: #1677ff" />
            </a-list-item>
          </template>
        </a-list>
      </div>
      <div v-if="selectedUser">
        <label style="display: block; margin-bottom: 8px; font-weight: 500">角色</label>
        <a-select v-model:value="newMemberRole" style="width: 200px">
          <a-select-option value="admin">管理员</a-select-option>
          <a-select-option value="developer">开发者</a-select-option>
          <a-select-option value="tester">测试</a-select-option>
        </a-select>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { message } from 'ant-design-vue'
import { PlusOutlined, CheckOutlined } from '@ant-design/icons-vue'
import {
  getMembers, searchUsers, addMember, updateMemberRole, removeMember,
  type ProjectMember, type UserSearchResult,
} from '@/api/projectMembers'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const userStore = useUserStore()

const projectId = computed(() => Number(route.params.id))

const members = ref<ProjectMember[]>([])
const loading = ref(false)

const canManage = ref(false)

const columns = [
  { title: '用户', key: 'username', dataIndex: 'username' },
  { title: '邮箱', key: 'email', dataIndex: 'email' },
  { title: '角色', key: 'role', dataIndex: 'role' },
  { title: '加入时间', key: 'joined_at', dataIndex: 'joined_at', customRender: ({ text }: { text: string }) => text ? new Date(text).toLocaleString('zh-CN') : '' },
  { title: '操作', key: 'action', width: 200 },
]

const roleLabels: Record<string, string> = {
  owner: '创建者',
  admin: '管理员',
  developer: '开发者',
  tester: '测试',
}

const roleColors: Record<string, string> = {
  owner: 'purple',
  admin: 'red',
  developer: 'blue',
  tester: 'green',
}

const addModalVisible = ref(false)
const addLoading = ref(false)
const searchKeyword = ref('')
const searchLoading = ref(false)
const searchResults = ref<UserSearchResult[]>([])
const selectedUser = ref<UserSearchResult | null>(null)
const newMemberRole = ref('tester')

async function loadMembers() {
  loading.value = true
  try {
    members.value = await getMembers(projectId.value)
    const currentMember = members.value.find(m => m.user_id === userStore.userInfo?.id)
    canManage.value = userStore.userInfo?.is_admin === true ||
      (currentMember != null && (currentMember.role === 'owner' || currentMember.role === 'admin'))
  } catch {
    message.error('加载成员列表失败')
  } finally {
    loading.value = false
  }
}

async function handleSearch() {
  if (!searchKeyword.value.trim()) return
  searchLoading.value = true
  try {
    searchResults.value = await searchUsers(projectId.value, searchKeyword.value.trim())
    if (searchResults.value.length === 0) {
      message.info('未找到匹配的用户')
    }
  } catch {
    message.error('搜索用户失败')
  } finally {
    searchLoading.value = false
  }
}

function showAddModal() {
  addModalVisible.value = true
  searchKeyword.value = ''
  searchResults.value = []
  selectedUser.value = null
  newMemberRole.value = 'tester'
}

async function handleAdd() {
  if (!selectedUser.value) {
    message.warning('请先选择用户')
    return
  }
  addLoading.value = true
  try {
    await addMember(projectId.value, {
      user_id: selectedUser.value.id,
      role: newMemberRole.value,
    })
    message.success('成员添加成功')
    addModalVisible.value = false
    await loadMembers()
  } catch (e: any) {
    const detail = e?.response?.data?.detail || e?.message || '添加失败'
    message.error(detail)
  } finally {
    addLoading.value = false
  }
}

async function handleRoleChange(record: ProjectMember, newRole: string) {
  if (newRole === record.role) return
  try {
    await updateMemberRole(projectId.value, record.user_id, newRole)
    message.success('角色已更新')
    await loadMembers()
  } catch (e: any) {
    const detail = e?.response?.data?.detail || e?.message || '更新失败'
    message.error(detail)
  }
}

async function handleRemove(record: ProjectMember) {
  try {
    await removeMember(projectId.value, record.user_id)
    message.success('成员已移除')
    await loadMembers()
  } catch (e: any) {
    const detail = e?.response?.data?.detail || e?.message || '移除失败'
    message.error(detail)
  }
}

onMounted(() => {
  loadMembers()
})
</script>

<style scoped>
.project-members {
  padding: 0;
}
.selected-user {
  background-color: #e6f4ff;
}
</style>
