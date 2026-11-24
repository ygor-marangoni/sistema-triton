import { useEffect, useRef } from 'react'
import { X } from 'lucide-react'

export default function AppDialog({ title, busy, onClose, children }) {
  const ref = useRef(null)
  useEffect(() => { const dialog = ref.current; if (!dialog.open) dialog.showModal(); return () => { if (dialog.open) dialog.close() } }, [])
  return <dialog ref={ref} className="app-dialog" aria-labelledby="app-dialog-title" onCancel={(event) => { event.preventDefault(); if (!busy) onClose() }}><div className="app-dialog-header"><h2 id="app-dialog-title">{title}</h2><button type="button" aria-label="Fechar" disabled={busy} onClick={onClose}><X size={19} aria-hidden="true" /></button></div>{children}</dialog>
}
