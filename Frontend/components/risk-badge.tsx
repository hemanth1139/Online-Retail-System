import { cn } from '@/lib/utils'
import type { RiskLevel } from '@/lib/types'

export const RISK_LEVELS: RiskLevel[] = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']

export const riskColor: Record<RiskLevel, string> = {
  CRITICAL: 'var(--risk-critical)',
  HIGH: 'var(--risk-high)',
  MEDIUM: 'var(--risk-medium)',
  LOW: 'var(--risk-low)',
}

export const riskStyles: Record<RiskLevel, { badge: string; dot: string; bar: string }> = {
  CRITICAL: {
    badge: 'bg-risk-critical/10 text-risk-critical ring-risk-critical/25',
    dot: 'bg-risk-critical',
    bar: 'bg-risk-critical',
  },
  HIGH: {
    badge: 'bg-risk-high/10 text-risk-high ring-risk-high/25',
    dot: 'bg-risk-high',
    bar: 'bg-risk-high',
  },
  MEDIUM: {
    badge: 'bg-risk-medium/10 text-risk-medium ring-risk-medium/30',
    dot: 'bg-risk-medium',
    bar: 'bg-risk-medium',
  },
  LOW: {
    badge: 'bg-risk-low/10 text-risk-low ring-risk-low/25',
    dot: 'bg-risk-low',
    bar: 'bg-risk-low',
  },
}

export function RiskBadge({ level, className }: { level: RiskLevel; className?: string }) {
  const styles = riskStyles[level]
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset',
        styles.badge,
        className,
      )}
    >
      <span className="relative flex size-1.5">
        {level === 'CRITICAL' && (
          <span
            className={cn(
              'absolute inline-flex size-full animate-ping rounded-full opacity-75 motion-reduce:animate-none',
              styles.dot,
            )}
          />
        )}
        <span className={cn('relative inline-flex size-1.5 rounded-full', styles.dot)} />
      </span>
      {level.charAt(0) + level.slice(1).toLowerCase()}
    </span>
  )
}
