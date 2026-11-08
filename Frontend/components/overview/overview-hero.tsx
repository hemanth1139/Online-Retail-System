import Link from 'next/link'
import { ArrowRight, CalendarDays } from 'lucide-react'
import type { DashboardSummary } from '@/lib/types'
import { cn } from '@/lib/utils'
import { Panel } from '@/components/data-state'
import { RingGauge } from '@/components/ring-gauge'

export function OverviewHero({ summary }: { summary: DashboardSummary }) {
  const { total_active_skus, critical_high_count, risk_distribution } = summary
  const healthy = risk_distribution.LOW + risk_distribution.MEDIUM
  const healthyShare = total_active_skus > 0 ? (healthy / total_active_skus) * 100 : 0
  const needsAction = critical_high_count > 0

  return (
    <Panel className="animate-rise relative overflow-hidden p-6 sm:p-8">
      <div className="flex flex-col gap-8 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex max-w-xl flex-col gap-5">
          <span className="inline-flex w-fit items-center gap-2 rounded-full border bg-background/60 px-3 py-1 text-xs font-medium text-muted-foreground">
            <CalendarDays className="size-3.5" aria-hidden="true" />
            Today&apos;s briefing
          </span>
          <h1 className="text-balance text-3xl font-semibold leading-tight tracking-tight sm:text-4xl">
            {needsAction ? (
              <>
                <span className="text-risk-critical">{critical_high_count.toLocaleString()}</span> of{' '}
                {total_active_skus.toLocaleString()} SKUs need a reorder decision
              </>
            ) : (
              <>All {total_active_skus.toLocaleString()} SKUs are comfortably stocked</>
            )}
          </h1>
          <p className="text-pretty text-sm leading-relaxed text-muted-foreground sm:text-base">
            {needsAction
              ? 'These products are likely to run out before a new order can arrive. Review the suggested quantities and raise purchase orders before lead time runs out.'
              : 'No product is expected to stock out within its supplier lead time. Check back after the next forecast run.'}
          </p>
          <div className="flex flex-wrap gap-3">
            <Link
              href="/recommendations"
              className="inline-flex h-10 items-center gap-2 rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
            >
              Review recommendations
              <ArrowRight className="size-4" aria-hidden="true" />
            </Link>
            <Link
              href="/inventory"
              className="inline-flex h-10 items-center rounded-lg border bg-background px-4 text-sm font-medium transition-colors hover:bg-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
            >
              Inspect inventory
            </Link>
          </div>
        </div>

        <div className="flex items-center gap-6 rounded-xl border bg-background/50 p-5">
          <RingGauge value={healthyShare} size={132} stroke={12} label={`${Math.round(healthyShare)} percent of SKUs are healthy`}>
            <span className="text-3xl font-semibold tabular-nums tracking-tight">{Math.round(healthyShare)}%</span>
            <span className="text-xs text-muted-foreground">healthy</span>
          </RingGauge>
          <dl className="flex flex-col gap-3 text-sm">
            {(
              [
                ['Low risk', risk_distribution.LOW, 'bg-risk-low'],
                ['Medium risk', risk_distribution.MEDIUM, 'bg-risk-medium'],
                ['High risk', risk_distribution.HIGH, 'bg-risk-high'],
                ['Critical', risk_distribution.CRITICAL, 'bg-risk-critical'],
              ] as const
            ).map(([label, count, dot]) => (
              <div key={label} className="flex items-center gap-3">
                <span className={cn('size-2 rounded-full', dot)} aria-hidden="true" />
                <dt className="w-24 text-muted-foreground">{label}</dt>
                <dd className="font-medium tabular-nums">{count.toLocaleString()}</dd>
              </div>
            ))}
          </dl>
        </div>
      </div>
    </Panel>
  )
}
