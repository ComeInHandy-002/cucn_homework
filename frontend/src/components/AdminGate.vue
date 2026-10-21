<script setup>
import { ref } from 'vue'
import { adminApi, isAdminLoggedIn, currentAdmin } from '../adminApi'

const emit = defineEmits(['logged-in'])

const props = defineProps({
  title: { type: String, default: '后台管理域登录' }
})

const loggedIn = ref(isAdminLoggedIn())
const adminUser = ref(currentAdmin())
const form = ref({ username: 'admin', password: 'admin123' })
const busy = ref(false)
const status = ref('演示账号：admin / admin123')

async function handleLogin() {
  busy.value = true
  status.value = '正在验证...'
  try {
    const data = await adminApi.login(form.value.username, form.value.password)
    adminUser.value = data.user
    loggedIn.value = true
    emit('logged-in', data.user)
  } catch {
    status.value = '登录失败，请检查账号'
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div v-if="loggedIn">
    <slot :admin="adminUser" />
  </div>
  <section v-else>
    <div class="page-intro">
      <div><span class="section-label">ADMIN ACCESS</span><h2>{{ props.title }}</h2><p>该页面属于后台管理域（Spring Boot 服务），需要管理域账号登录。</p></div>
    </div>
    <article class="panel" style="max-width: 460px; margin: 0 auto">
      <form style="display: grid; gap: 14px; padding: 26px 26px 20px" @submit.prevent="handleLogin">
        <label style="display: grid; gap: 6px"><span style="color:#64788b;font-size:11px">用户名</span>
          <input v-model="form.username" style="padding: 9px 10px; border: 1px solid #dce5ec; border-radius: 7px" />
        </label>
        <label style="display: grid; gap: 6px"><span style="color:#64788b;font-size:11px">密码</span>
          <input v-model="form.password" type="password" style="padding: 9px 10px; border: 1px solid #dce5ec; border-radius: 7px" />
        </label>
        <button class="primary full-button" type="submit" :disabled="busy">{{ busy ? '验证中...' : '登录管理域 →' }}</button>
        <p style="margin: 0; color: #98a5b2; font-size: 10px; text-align: center">{{ status }}</p>
      </form>
    </article>
  </section>
</template>
