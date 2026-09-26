import { defineStore } from 'pinia'
import { ElNotification } from 'element-plus'
import * as api from './api'
import { eventLabel, eventIcon } from './utils'

function notify(title, message, type = 'info') {
  ElNotification({ title, message, type, duration: 4200 })
}

export const useAppStore = defineStore('app', {
  state: () => ({
    token: localStorage.getItem('safety_token') || '',
    user: JSON.parse(localStorage.getItem('safety_user') || 'null'),
    health: null,
    healthError: '',
    metrics: null,
    cameras: [],
    zones: [],
    demoAssets: [],
    events: [],
    jobs: [],
    experimentSummary: null,
    socket: null,
    socketOnline: false,
    // Shared modal payloads so alerts and job pages can open the same dialogs.
    evidenceEvent: null,
    jobResult: null
  }),

  getters: {
    isLoggedIn: (state) => Boolean(state.token),
    cameraName: (state) => (cameraId) => {
      if (cameraId === null || cameraId === undefined) return '未绑定监控点'
      const camera = state.cameras.find((item) => String(item.id) === String(cameraId))
      return camera ? camera.name : `监控点 ${cameraId}`
    },
    openEventCount: (state) => (state.metrics ? state.metrics.open_events : 0)
  },

  actions: {
    async boot() {
      await this.refreshHealth()
      if (!this.token) return
      try {
        await this.refreshAll()
        this.connectWS()
      } catch (error) {
        if (error.status === 401) {
          this.logout(false)
          notify('登录已过期', '请重新登录监测平台', 'warning')
        } else {
          notify('工作台数据加载失败', error.message, 'error')
        }
      }
    },

    async login(username, password) {
      const data = await api.login(username, password)
      this.token = data.access_token
      this.user = data.user
      localStorage.setItem('safety_token', this.token)
      localStorage.setItem('safety_user', JSON.stringify(this.user))
      await this.refreshAll()
      this.connectWS()
    },

    logout(showMessage = true) {
      this.token = ''
      this.user = null
      localStorage.removeItem('safety_token')
      localStorage.removeItem('safety_user')
      this.disconnectWS()
      if (showMessage) notify('已退出系统', '登录令牌已从当前浏览器清除', 'info')
    },

    async refreshHealth() {
      try {
        this.health = await api.health()
        this.healthError = ''
      } catch (error) {
        this.health = null
        this.healthError = error.message
      }
    },

    async refreshMetrics() {
      if (!this.token) return
      this.metrics = await api.metrics()
    },

    async refreshCameras() {
      if (!this.token) return
      this.cameras = await api.listCameras()
    },

    async refreshZones() {
      if (!this.token) return
      this.zones = await api.listZones()
    },

    async refreshDemoAssets() {
      if (!this.token) return
      this.demoAssets = await api.listDemoAssets()
    },

    async refreshEvents() {
      if (!this.token) return
      this.events = await api.listEvents({ limit: 100 })
    },

    async refreshJobs() {
      if (!this.token) return
      this.jobs = await api.listJobs({ limit: 100 })
    },

    async refreshExperiments() {
      if (!this.token) return
      this.experimentSummary = await api.experiments()
    },

    async refreshAll() {
      await this.refreshCameras()
      await Promise.all([
        this.refreshMetrics(),
        this.refreshEvents(),
        this.refreshJobs(),
        this.refreshDemoAssets(),
        this.refreshZones()
      ])
    },

    async updateEventStatus(eventId, status) {
      await api.updateEvent(eventId, status)
      await Promise.all([this.refreshEvents(), this.refreshMetrics()])
      notify('事件状态已更新', status === 'resolved' ? '该事件已完成闭环处理' : '该事件已由人工确认', 'success')
    },

    async removeZone(zoneId) {
      await api.deleteZone(zoneId)
      await this.refreshZones()
      notify('危险区域已删除', '该区域不再参与越界判断', 'success')
    },

    async openJobResult(jobId) {
      this.jobResult = await api.jobResult(jobId)
    },

    connectWS() {
      this.disconnectWS()
      if (!this.token) return
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const socket = new WebSocket(`${protocol}//${window.location.host}/api/v1/ws/events?token=${encodeURIComponent(this.token)}`)
      this.socket = socket
      socket.addEventListener('open', () => {
        this.socketOnline = true
        this._pingTimer = setInterval(() => {
          if (socket.readyState === WebSocket.OPEN) socket.send('ping')
        }, 25000)
      })
      socket.addEventListener('message', (message) => {
        let payload
        try {
          payload = JSON.parse(message.data)
        } catch {
          return
        }
        if (payload.type !== 'event' || !payload.event) return
        const event = payload.event
        if (this.events.some((item) => item.id === event.id)) return
        this.events.unshift(event)
        this.refreshMetrics().catch(() => {})
        ElNotification({
          title: '收到实时安全告警',
          message: `${eventLabel(event.event_type)} · ${this.cameraName(event.camera_id)}`,
          type: 'warning',
          duration: 6500
        })
      })
      socket.addEventListener('close', () => {
        clearInterval(this._pingTimer)
        this.socketOnline = false
        if (this.token) this._reconnectTimer = setTimeout(() => this.connectWS(), 3500)
      })
      socket.addEventListener('error', () => {
        this.socketOnline = false
      })
    },

    disconnectWS() {
      clearTimeout(this._reconnectTimer)
      clearInterval(this._pingTimer)
      if (this.socket) {
        this.socket.onclose = null
        this.socket.close()
        this.socket = null
      }
      this.socketOnline = false
    },

    notify
  }
})
