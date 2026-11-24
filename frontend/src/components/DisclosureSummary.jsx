import { ChevronRight } from 'lucide-react'

export default function DisclosureSummary({ children }) {
  return (
    <summary>
      <ChevronRight className="disclosure-chevron" size={16} strokeWidth={2} aria-hidden="true" />
      <span>{children}</span>
    </summary>
  )
}
