import axios from 'axios'

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8013',
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
})

export function errorMessage(error) {
  const detail = error?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map((entry) => entry.msg).join('; ')
  return 'Não foi possível concluir. Verifique a conexão com a API e tente novamente.'
}
