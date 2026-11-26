import { ChevronLeft, ChevronRight } from 'lucide-react'

export function IntegrationHeader({ title, description }) {
  return <div className="integration-heading"><div><h3>{title}</h3><p>{description}</p></div></div>
}

export function IntegrationField({ label, hint, children, className = '' }) {
  return <label className={`field integration-field ${className}`}><span>{label}</span>{children}{hint && <small>{hint}</small>}</label>
}

export function IntegrationPagination({ page, count, size, onPage }) {
  return <div className="integration-pagination"><span>Página {page + 1} · {count} {count === 1 ? 'registro' : 'registros'}{count === size ? ' · pode haver mais' : ''}</span><div><button type="button" className="integration-page-button" aria-label="Página anterior" disabled={page === 0} onClick={() => onPage(page - 1)}><ChevronLeft size={16} /></button><button type="button" className="integration-page-button" aria-label="Próxima página" disabled={count < size} onClick={() => onPage(page + 1)}><ChevronRight size={16} /></button></div></div>
}

export function IntegrationNotice({ type = 'info', children }) {
  return children ? <div className={`integration-notice ${type}`} role={type === 'error' ? 'alert' : 'status'}>{children}</div> : null
}

export function IntegrationEmpty({ icon: Icon, title, children }) {
  return <div className="integration-empty"><span className="integration-empty-icon"><Icon size={21} strokeWidth={1.6} aria-hidden="true" /></span><div><strong>{title}</strong><p>{children}</p></div></div>
}
