import { ArrowRight } from 'lucide-react'

export default function MonitoringEmptyState({ icon: Icon, label, title, description, note, actionLabel, onAction }) {
  return <section className="monitoring-empty">
    <div className="monitoring-empty-main">
      <span className="monitoring-empty-icon"><Icon size={23} strokeWidth={1.8} aria-hidden="true" /></span>
      <div className="monitoring-empty-copy">
        <span className="monitoring-empty-label">{label}</span>
        <h3>{title}</h3>
        <p>{description}</p>
        {note && <small>{note}</small>}
      </div>
    </div>
    <button type="button" className="button secondary monitoring-empty-action" onClick={onAction}>{actionLabel}<ArrowRight size={16} aria-hidden="true" /></button>
  </section>
}
