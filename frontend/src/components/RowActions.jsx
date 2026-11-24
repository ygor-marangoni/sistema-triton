import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { MoreVertical } from 'lucide-react'

export default function RowActions({ name, actions }) {
  const [position, setPosition] = useState(null)
  const trigger = useRef(null)
  const menu = useRef(null)
  useEffect(() => {
    if (!position) return undefined
    const dismiss = (event) => { if (!trigger.current?.contains(event.target) && !menu.current?.contains(event.target)) setPosition(null) }
    const keydown = (event) => { if (event.key === 'Escape') { setPosition(null); trigger.current?.focus() } }
    const scroll = () => setPosition(null)
    document.addEventListener('pointerdown', dismiss)
    document.addEventListener('keydown', keydown)
    window.addEventListener('scroll', scroll, true)
    window.addEventListener('resize', scroll)
    menu.current?.querySelector('button')?.focus()
    return () => { document.removeEventListener('pointerdown', dismiss); document.removeEventListener('keydown', keydown); window.removeEventListener('scroll', scroll, true); window.removeEventListener('resize', scroll) }
  }, [position])
  const open = () => {
    if (position) { setPosition(null); return }
    const rect = trigger.current.getBoundingClientRect()
    setPosition({ top: Math.max(8, Math.min(rect.bottom + 6, window.innerHeight - actions.length * 42 - 20)), left: Math.max(8, Math.min(rect.right - 168, window.innerWidth - 176)) })
  }
  const invoke = (action) => { setPosition(null); action.onClick() }
  return <><div className="row-actions-desktop"><button ref={trigger} type="button" className="row-menu-trigger" aria-label={`Ações para ${name}`} aria-expanded={Boolean(position)} aria-haspopup="menu" onClick={open}><MoreVertical size={18} aria-hidden="true" /></button>{position && createPortal(<div ref={menu} className="row-menu" style={position} role="menu">{actions.map((action) => <button key={action.label} type="button" role="menuitem" className={action.danger ? 'is-danger' : ''} onClick={() => invoke(action)}>{action.Icon && <action.Icon size={16} aria-hidden="true" />}{action.label}</button>)}</div>, document.body)}</div><div className="row-actions-mobile">{actions.map((action) => <button key={action.label} type="button" className={action.danger ? 'is-danger' : ''} onClick={() => action.onClick()}>{action.label}</button>)}</div></>
}
