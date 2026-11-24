import { useEffect, useRef, useState } from 'react'
import { Check, ChevronsUpDown, MapPin, Plus } from 'lucide-react'

export default function PropertySwitcher({ properties, selected, onSelect, onCreate, collapsed, onExpand }) {
  const [open, setOpen] = useState(false)
  const root = useRef(null)
  useEffect(() => {
    if (!open) return undefined
    function dismiss(event) {
      if (!root.current?.contains(event.target)) setOpen(false)
    }
    function escape(event) {
      if (event.key === 'Escape') {
        setOpen(false)
        root.current?.querySelector('.property-switcher-trigger')?.focus()
      }
    }
    document.addEventListener('pointerdown', dismiss)
    document.addEventListener('keydown', escape)
    return () => {
      document.removeEventListener('pointerdown', dismiss)
      document.removeEventListener('keydown', escape)
    }
  }, [open])

  return <div className="property-switcher" ref={root}>
    <button type="button" className="property-switcher-trigger" aria-expanded={open} aria-label={selected ? `Propriedade atual: ${selected.name}. Trocar propriedade` : 'Selecionar propriedade'} onClick={() => { if (collapsed) onExpand(); setOpen((value) => !value) }}>
      <span className="property-switcher-art"><img src="/images/property-switcher.png" alt="" /></span>
      <span className="property-switcher-copy"><span>PROPRIEDADE</span><strong>{selected?.name || 'Selecionar propriedade'}</strong></span>
      <ChevronsUpDown className="property-switcher-chevron" size={17} aria-hidden="true" />
    </button>
    {open && <div className="property-switcher-menu" aria-label="Propriedades disponíveis">
      <div className="property-switcher-menu-title">Suas propriedades <span>{properties.length}</span></div>
      <div className="property-switcher-options">
        {properties.length ? properties.map((property) => <button type="button" key={property.id} className={`property-switcher-option${selected?.id === property.id ? ' is-selected' : ''}`} onClick={() => { onSelect(property); setOpen(false) }}>
          <span className="property-switcher-option-icon"><MapPin size={16} aria-hidden="true" /></span>
          <span className="property-switcher-option-copy"><strong>{property.name}</strong><small>{property.city}/{property.state}</small></span>
          {selected?.id === property.id && <Check size={16} aria-label="Selecionada" />}
        </button>) : <p className="property-switcher-empty">Você ainda não cadastrou propriedades.</p>}
      </div>
      <button type="button" className="property-switcher-create" onClick={() => { setOpen(false); onCreate() }}><Plus size={17} aria-hidden="true" /> Cadastrar propriedade</button>
    </div>}
  </div>
}
