export const EVENT_TYPES = {
  no_helmet: { label: '未佩戴安全帽', icon: '帽' },
  no_vest: { label: '未穿反光背心', icon: '服' },
  intrusion: { label: '危险区域闯入', icon: '界' }
}

export const SEVERITY_LABELS = { critical: '严重', high: '高危', medium: '中危', low: '低危' }
export const STATUS_LABELS = { open: '待处理', acknowledged: '已确认', resolved: '已关闭' }
export const JOB_STATUS_LABELS = { queued: '排队中', running: '执行中', completed: '已完成', failed: '失败' }
export const JOB_SOURCE_LABELS = { image: '图片', video: '视频' }

export const CLASS_LABELS = {
  person: '人员',
  helmet: '安全帽',
  hardhat: '安全帽',
  hard_hat: '安全帽',
  safety_helmet: '安全帽',
  vest: '反光背心',
  safety_vest: '反光背心',
  reflective_vest: '反光背心'
}

export function eventLabel(type) {
  return EVENT_TYPES[type]?.label || type
}

export function eventIcon(type) {
  return EVENT_TYPES[type]?.icon || '!'
}

export function classLabel(name) {
  return CLASS_LABELS[String(name || '').trim().toLowerCase()] || name
}

export function formatDateTime(value) {
  if (!value) return { time: '--:--:--', date: '----/--/--' }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return { time: '--:--:--', date: '----/--/--' }
  return {
    time: date.toLocaleTimeString('zh-CN', { hour12: false }),
    date: date.toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' })
  }
}

// Backend result/preview paths may be absolute Windows paths; only the part
// after "/results/" is exposed through the FastAPI static mount.
export function pathToUrl(path) {
  if (!path) return ''
  const normalized = String(path).replaceAll('\\', '/')
  const markerIndex = normalized.lastIndexOf('/results/')
  if (markerIndex >= 0) return normalized.slice(markerIndex)
  if (normalized.startsWith('results/')) return `/${normalized}`
  return normalized
}

export function isVideoPreview(path) {
  return /\.(mp4|webm|ogv)(?:\?|$)/i.test(String(path || ''))
}

export function formatMetric(value) {
  return value === null || value === undefined ? '--' : Number(value).toFixed(3)
}
