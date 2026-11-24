import { useEffect, useId, useRef, useState } from 'react'
import { Check, ChevronDown } from 'lucide-react'

const options = [{ value: 'open', label: 'Em aberto' }, { value: 'resolved', label: 'Resolvidos' }]

export default function AlertStatusSelect({ value, onChange }) {
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const root = useRef(null)
  const id = useId()
  const index = Math.max(0, options.findIndex((item) => item.value === value))

  useEffect(() => {
    if (!open) return undefined
    const close = (event) => { if (!root.current?.contains(event.target)) setOpen(false) }
    document.addEventListener('pointerdown', close)
    return () => document.removeEventListener('pointerdown', close)
  }, [open])

  function selectOption(optionIndex) {
    onChange(options[optionIndex].value)
    setOpen(false)
    root.current?.querySelector('button')?.focus()
  }

  function handleKey(event) {
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault()
      if (!open) { setActive(index); setOpen(true); return }
      setActive((current) => (current + (event.key === 'ArrowDown' ? 1 : -1) + options.length) % options.length)
    } else if (event.key === 'Escape' && open) {
      event.preventDefault(); setOpen(false)
    } else if ((event.key === 'Enter' || event.key === ' ') && open) {
      event.preventDefault(); selectOption(active)
    } else if (event.key === 'Tab') setOpen(false)
  }

  return <div className="alert-filter" ref={root}>
    <button type="button" role="combobox" className="alert-filter-trigger" aria-label="Exibir alertas" aria-haspopup="listbox" aria-expanded={open} aria-controls={open ? `${id}-list` : undefined} aria-activedescendant={open ? `${id}-option-${active}` : undefined} onKeyDown={handleKey} onClick={() => { setActive(index); setOpen((current) => !current) }}>
      {options[index].label}<ChevronDown size={16} aria-hidden="true" />
    </button>
    {open && <ul id={`${id}-list`} role="listbox" aria-label="Estado dos alertas" className="alert-filter-options">
      {options.map((option, optionIndex) => <li key={option.value} id={`${id}-option-${optionIndex}`} role="option" aria-selected={option.value === value} className={optionIndex === active ? 'is-active' : ''} onMouseEnter={() => setActive(optionIndex)} onMouseDown={(event) => event.preventDefault()} onClick={() => selectOption(optionIndex)}><span>{option.label}</span>{option.value === value && <Check size={15} aria-hidden="true" />}</li>)}
    </ul>}
  </div>
}
