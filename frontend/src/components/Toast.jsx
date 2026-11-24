import { useEffect } from 'react'
import { AlertCircle, CheckCircle2, X } from 'lucide-react'

export default function Toast({ message, kind = 'success', onDismiss }) {
  useEffect(() => {
    if (!message) return undefined
    const timer = window.setTimeout(() => onDismiss(''), kind === 'error' ? 10000 : 6000)
    return () => window.clearTimeout(timer)
  }, [message, kind, onDismiss])

  if (!message) return null
  const Icon = kind === 'error' ? AlertCircle : CheckCircle2
  return <div className={`app-toast app-toast--${kind}`} role={kind === 'error' ? 'alert' : 'status'}>
    <Icon size={19} aria-hidden="true" />
    <span>{message}</span>
    <button type="button" onClick={() => onDismiss('')} aria-label="Fechar notificação"><X size={16} aria-hidden="true" /></button>
  </div>
}
