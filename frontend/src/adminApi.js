// 后台管理域（Spring Boot :8081）的 Axios 封装：统一携带 JWT、
// 统一解包 {code, message, data}、错误统一 ElNotification 提示。
import axios from 'axios'
import { ElNotification } from 'element-plus'

const http = axios.create({
  baseURL: 'http://127.0.0.1:8081',
  timeout: 15000
})

http.interceptors.request.use((config) => {
  const token = localStorage.getItem('admin_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

http.interceptors.response.use(
  (response) => {
    const payload = response.data
    if (payload && typeof payload === 'object' && 'code' in payload) {
      if (payload.code !== 0) {
        ElNotification({ title: '操作失败', message: payload.message, type: 'error', duration: 4500 })
        return Promise.reject(new Error(payload.message))
      }
      return payload.data
    }
    return payload
  },
  (error) => {
    const status = error.response?.status
    const message = error.response?.data?.message || error.message
    ElNotification({
      title: status === 401 ? '登录已过期' : '请求失败',
      message,
      type: status === 401 ? 'warning' : 'error',
      duration: 4500
    })
    if (status === 401) {
      localStorage.removeItem('admin_token')
      localStorage.removeItem('admin_user')
    }
    return Promise.reject(error)
  }
)

export const adminApi = {
  async login(username, password) {
    const data = await http.post('/auth/login', { username, password })
    localStorage.setItem('admin_token', data.token)
    localStorage.setItem('admin_user', JSON.stringify(data.user))
    return data
  },

  register(username, password, realName, email) {
    return http.post('/auth/register', { username, password, realName, email })
  },

  me() {
    return http.get('/auth/me')
  },

  listUsers() {
    return http.get('/api/users')
  },

  createUser(payload) {
    return http.post('/api/users', payload)
  },

  updateUser(id, payload) {
    return http.put(`/api/users/${id}`, payload)
  },

  deleteUser(id) {
    return http.delete(`/api/users/${id}`)
  },

  uploadDataset(file, name, note) {
    const form = new FormData()
    form.append('file', file)
    if (name) form.append('name', name)
    if (note) form.append('note', note)
    return http.post('/api/datasets', form, { timeout: 300000 })
  },

  listDatasets() {
    return http.get('/api/datasets')
  },

  datasetDetail(id) {
    return http.get(`/api/datasets/${id}`)
  },

  deleteDataset(id) {
    return http.delete(`/api/datasets/${id}`)
  },

  startTraining(name, datasetTag) {
    return http.post('/api/models/train', { name, datasetTag }, { timeout: 30000 })
  },

  trainingStatus(id) {
    return http.get(`/api/models/train/${id}`)
  },

  listTrainingTasks() {
    return http.get('/api/models/train')
  },

  latestEvaluation() {
    return http.get('/api/models/evaluation')
  }
}

export function isAdminLoggedIn() {
  return Boolean(localStorage.getItem('admin_token'))
}

export function currentAdmin() {
  try {
    return JSON.parse(localStorage.getItem('admin_user') || 'null')
  } catch {
    return null
  }
}
