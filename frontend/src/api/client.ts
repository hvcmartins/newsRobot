import axios from 'axios'

const client = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '',
  timeout: 180_000,
})

client.interceptors.response.use(
  (r) => r,
  (err) => {
    const detail = err.response?.data?.detail
    let msg: string
    if (Array.isArray(detail)) {
      // FastAPI validation errors: [{loc, msg, type}, ...]
      msg = detail.map((d: { msg?: string }) => d.msg ?? JSON.stringify(d)).join(', ')
    } else {
      msg = detail || err.message || 'Request failed'
    }
    return Promise.reject(new Error(String(msg)))
  }
)

export default client
