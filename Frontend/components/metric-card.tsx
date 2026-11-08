import type { LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Panel, Skeleton } from '@/components/data-state'
import { Meter } from '@/components/meter'

export function MetricCard({
  label,
  value,
  hint,
  icon: Icon,
  tone = 'default',
  meter,
  delay = 0,
}: {
  label: string
  value: React.ReactNode
  hint: React.ReactNode
  icon: LucideIcon
  tone?: 'default' | 'danger'
  meter?: { value: number; label: string }
  delay?: number
}) {
  const danger = tone === 'danger'

  return (
    <Panel
      className={cn('animate-rise flex flex-col gap-4 p-5', danger && 'border-risk-critical/30')}
      style={{ animationDelay: `${delay}ms` }}
    >
      <div className="flex items-start justify-between gap-3">
        <h2 className="text-sm font-medium text-muted-foreground">{label}</h2>
        <span
          className={cn(
            'flex size-9 items-center justify-center rounded-lg',
            danger ? 'bg-risk-critical/10 text-risk-critical' : 'bg-primary/10 text-primary',
          )}
        >
          <Icon className="size-4.5" aria-hidden="true" />
        </span>
      </div>
      <div>
        <p className="text-3xl font-semibold tabular-nums tracking-tight">{value}</p>
        <p className="mt-1 text-xs text-muted-foreground">{hint}</p>
      </div>
      {meter && <Meter value={meter.value} label={meter.label} barClassName={danger ? 'bg-risk-critical' : undefined} />}
    </Panel>
  )
}

export function MetricCardSkeleton() {
  return (
    <Panel className="p-5">
      <div className="flex items-start justify-between">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="size-9" />
      </div>
      <Skeleton className="mt-5 h-8 w-20" />
      <Skeleton className="mt-3 h-3 w-32" />
    </Panel>
  )
}
