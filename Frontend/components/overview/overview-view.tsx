'use client'

import Link from 'next/link'
import { ArrowRight, Boxes, ShieldAlert, Target, TrendingUp } from 'lucide-react'
import { useDashboardSummary } from '@/lib/api'
import { ErrorState, Panel, Skeleton } from '@/components/data-state'
import { MetricCard, MetricCardSkeleton } from '@/components/metric-card'
import { OverviewHero } from '@/components/overview/overview-hero'
import { PriorityActions } from '@/components/overview/priority-actions'
import { RiskDistribution } from '@/components/overview/risk-distribution'

const numberFormat = new Intl.NumberFormat('en-US')

export function OverviewView() {
  const { data, error } = useDashboardSummary()

  if (error) return <ErrorState error={error} message="Unable to load the dashboard summary." />

  const atRiskShare = data && data.total_active_skus > 0 ? (data.critical_high_count / data.total_active_skus) * 100 : 0
  const accuracy = data ? Math.max(0, 100 - data.forecast_accuracy.wape) : 0

  return (
    <>
      {data ? <OverviewHero summary={data} /> : <Skeleton className="h-64 w-full rounded-xl" />}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {data ? (
          <>
            <MetricCard
              label="Active SKUs"
              value={numberFormat.format(data.total_active_skus)}
              hint="Tracked across all suppliers"
              icon={Boxes}
              delay={0}
            />
            <MetricCard
              label="Critical / High risk"
              value={numberFormat.format(data.critical_high_count)}
              hint={`${atRiskShare.toFixed(0)}% of active SKUs`}
              icon={ShieldAlert}
              tone="danger"
              meter={{ value: atRiskShare, label: 'Share of SKUs at critical or high risk' }}
              delay={60}
            />
            <MetricCard
              label="30-day demand"
              value={numberFormat.format(data.projected_30d_demand)}
              hint="Projected units, all SKUs"
              icon={TrendingUp}
              delay={120}
            />
            <MetricCard
              label="Forecast accuracy"
              value={`${accuracy.toFixed(1)}%`}
              hint={`WAPE ${data.forecast_accuracy.wape.toFixed(1)}% · MAE ${data.forecast_accuracy.mae.toFixed(1)}`}
              icon={Target}
              meter={{ value: accuracy, label: 'Forecast accuracy, 100 minus WAPE' }}
              delay={180}
            />
          </>
        ) : (
          Array.from({ length: 4 }, (_, i) => <MetricCardSkeleton key={i} />)
        )}
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.5fr)]">
        <Panel className="animate-rise p-5" style={{ animationDelay: '240ms' }}>
          <h2 className="text-base font-semibold">Risk distribution</h2>
          <p className="mt-1 text-sm text-muted-foreground">Active SKUs by stockout risk level.</p>
          {data ? (
            <RiskDistribution distribution={data.risk_distribution} />
          ) : (
            <div className="mt-6 flex flex-col items-center gap-4">
              <Skeleton className="size-44 rounded-full" />
              <Skeleton className="h-16 w-full" />
            </div>
          )}
        </Panel>

        <Panel className="animate-rise p-5" style={{ animationDelay: '300ms' }}>
          <div className="flex items-start justify-between gap-4">
            <div>
              <h2 className="text-base font-semibold">Priority actions</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                Most urgent reorders, ranked by risk and shortfall.
              </p>
            </div>
            <Link
              href="/recommendations"
              className="inline-flex shrink-0 items-center gap-1.5 text-sm font-medium text-primary hover:underline"
            >
              View all
              <ArrowRight className="size-4" aria-hidden="true" />
            </Link>
          </div>
          {data ? (
            <PriorityActions actions={data.priority_actions} />
          ) : (
            <div className="mt-4 flex flex-col gap-3">
              {Array.from({ length: 4 }, (_, i) => (
                <Skeleton key={i} className="h-16 w-full" />
              ))}
            </div>
          )}
        </Panel>
      </div>
    </>
  )
}
