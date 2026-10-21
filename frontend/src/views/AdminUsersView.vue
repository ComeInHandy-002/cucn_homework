<script setup>
import { onMounted, reactive, ref } from 'vue'
import { adminApi, isAdminLoggedIn } from '../adminApi'
import AdminGate from '../components/AdminGate.vue'

const users = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const editingId = ref(null)
const form = reactive({ username: '', password: '', role: 'operator', realName: '', email: '', enabled: true })

async function refresh() {
  loading.value = true
  try {
    users.value = await adminApi.listUsers()
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingId.value = null
  Object.assign(form, { username: '', password: '', role: 'operator', realName: '', email: '', enabled: true })
  dialogVisible.value = true
}

function openEdit(user) {
  editingId.value = user.id
  Object.assign(form, { username: user.username, password: '', role: user.role, realName: user.realName || '', email: user.email || '', enabled: user.enabled })
  dialogVisible.value = true
}

async function submit() {
  try {
    if (editingId.value) {
      await adminApi.updateUser(editingId.value, {
        role: form.role, realName: form.realName, email: form.email, enabled: form.enabled,
        password: form.password || undefined
      })
    } else {
      await adminApi.createUser({ username: form.username, password: form.password, realName: form.realName, email: form.email })
    }
    dialogVisible.value = false
    await refresh()
  } catch {
    // 错误提示由 axios 拦截器统一弹出
  }
}

async function remove(user) {
  try {
    await adminApi.deleteUser(user.id)
    await refresh()
  } catch {
    // 拦截器已提示
  }
}

onMounted(async () => {
  if (isAdminLoggedIn()) await refresh()
})
</script>

<template>
  <AdminGate title="用户管理" @logged-in="refresh">
    <section>
    <div class="page-intro">
      <div><span class="section-label">USER MANAGEMENT</span><h2>用户管理</h2><p>后台管理域（Spring Boot + MySQL）的用户账号增删改查。</p></div>
      <button class="outline-button" type="button" @click="refresh">↻ 刷新</button>
    </div>

    <article class="panel">
      <div class="panel-heading">
        <div><span class="section-label">ACCOUNTS</span><h3>账号列表</h3></div>
        <button class="primary compact-button" type="button" @click="openCreate">＋ 新增用户</button>
      </div>
      <div class="table-scroll" v-loading="loading">
        <el-table :data="users" size="small" style="width:100%;min-width:760px">
          <el-table-column label="ID" width="64" prop="id" />
          <el-table-column label="用户名" width="140">
            <template #default="{ row }"><strong>{{ row.username }}</strong></template>
          </el-table-column>
          <el-table-column label="角色" width="110">
            <template #default="{ row }">
              <el-tag :type="row.role === 'admin' ? 'danger' : 'info'" effect="light" size="small">{{ row.role }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="姓名" width="120" prop="realName" />
          <el-table-column label="邮箱" min-width="180" prop="email" />
          <el-table-column label="状态" width="90">
            <template #default="{ row }">
              <el-tag :type="row.enabled ? 'success' : 'warning'" effect="light" size="small">{{ row.enabled ? '启用' : '停用' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="创建时间" width="120">
            <template #default="{ row }">{{ row.createdAt?.slice(0, 10) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="150">
            <template #default="{ row }">
              <div class="actions">
                <button type="button" @click="openEdit(row)">编辑</button>
                <button type="button" @click="remove(row)">删除</button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </article>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑用户' : '新增用户'" width="460px">
      <form class="form-grid" style="grid-template-columns: 1fr" @submit.prevent="submit">
        <label><span>用户名</span><input v-model="form.username" :disabled="Boolean(editingId)" required /></label>
        <label v-if="!editingId"><span>密码（至少 6 位）</span><input v-model="form.password" type="password" required minlength="6" /></label>
        <label v-else><span>重置密码（留空不修改）</span><input v-model="form.password" type="password" placeholder="留空表示不修改" /></label>
        <label><span>角色</span>
          <el-select v-model="form.role" style="width:100%">
            <el-option label="operator（操作员）" value="operator" />
            <el-option label="admin（管理员）" value="admin" />
          </el-select>
        </label>
        <label><span>姓名</span><input v-model="form.realName" /></label>
        <label><span>邮箱</span><input v-model="form.email" type="email" /></label>
        <label v-if="editingId"><span>启用状态</span>
          <el-switch v-model="form.enabled" />
        </label>
        <button class="primary" type="submit">保存</button>
      </form>
    </el-dialog>
  </section>
  </AdminGate>
</template>
