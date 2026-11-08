'use client'

import { useMemo, useState } from 'react'
import Link from 'next/link'
import { LineChart, PackageSearch } from 'lucide-react'
import { useInventoryRisks } from '@/lib/api'
import type { RiskLevel } from '@/lib/types'
import { cn } from '@/lib/utils'
import { ErrorState, Panel, Skeleton } from '@/components/data-state'
import { StockGauge } from '@/components/inventory/stock-gauge'
import { PageHeader } from '@/components/page-header'
import { RISK_LEVELS, RiskBadge, riskStyles } from '@/components/risk-badge'
import { SupplierChip } from '@/components/supplier-chip'

type Filter = RiskLevel | 'ALL'

const RISK_ORDER: Record<RiskLevel, number> = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3 }

export function InventoryView() {
  const { data, error } = useInventoryRisks()
  const [filter, setFilter] = useState<Filter>('ALL')

  const counts = useMemo(() => {
    const result: Record<Filter, number> = { ALL: data?.length ?? 0, CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0 }
    data?.forEach((item) => (result[item.risk_level] += 1))
    return result
  }, [data])

  const rows = useMemo(
    () =>
      (data ?? [])
        .filter((item) => filter === 'ALL' || item.risk_level === filter)
        .sort((a, b) => RISK_ORDER[a.risk_level] - RISK_ORDER[b.risk_level] || a.days_of_cover - b.days_of_cover),
    [data, filter],
  )

  const tiles: { value: Filter; label: string; bar?: string }[] = [
    { value: 'ALL', label: 'All SKUs' },
    ...RISK_LEVELS.map((level) => ({
      value: level as Filter,
      label: level.charAt(0) + level.slice(1).toLowerCase(),
      bar: riskStyles[level].bar,
    })),
  ]

  return (
    <>
      <PageHeader
        title="Inventory & Risks"
        description="Current stock position against safety stock and reorder points for every SKU."
      />

      {error ? (
        <ErrorState error={error} message="Unable to load inventory data." />
      ) : (
        <>
          <div role="group" aria-label="Filter by risk level" className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
            {tiles.map((tile, index) => {
              const selected = filter === tile.value
              const share = data && data.length > 0 ? (counts[tile.value] / data.length) * 100 : 0
              return (
                <button
                  key={tile.value}
                  type="button"
                  aria-pressed={selected}
                  onClick={() => setFilter(tile.value)}
                  style={{ animationDelay: `${index * 50}ms` }}
                  className={cn(
                    'animate-rise flex flex-col gap-3 rounded-xl border bg-card p-4 text-left shadow-xs transition-colors hover:bg-muted/40 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring',
                    selected && 'border-primary ring-1 ring-primary',
                  )}
                >
                  <span className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
                    {tile.bar && <span className={cn('size-2 rounded-full', tile.bar)} aria-hidden="true" />}
                    {tile.label}
                  </span>
                  <span className="text-2xl font-semibold tabular-nums tracking-tight">
                    {data ? counts[tile.value].toLocaleString() : '–'}
                  </span>
                  <span className="h-1 overflow-hidden rounded-full bg-muted" aria-hidden="true">
                    <span
                      className={cn('block h-full rounded-full transition-[width] duration-700', tile.bar ?? 'bg-primary')}
                      style={{ width: tile.value === 'ALL' ? '100%' : `${share}%` }}
                    />
                  </span>
                </button>
              )
            })}
          </div>

          <Panel className="animate-rise overflow-hidden" style={{ animationDelay: '260ms' }}>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[64rem] text-sm">
                <caption className="sr-only">Inventory levels and stockout risk by product</caption>
                <thead>
                  <tr className="border-b bg-muted/40 text-left text-xs uppercase tracking-wide text-muted-foreground">
                    <th scope="col" className="px-4 py-3 font-medium">Product</th>
                    <th scope="col" className="px-4 py-3 font-medium">Supplier</th>
                    <th scope="col" className="px-4 py-3 font-medium">Stock level</th>
                    <th scope="col" className="px-4 py-3 text-right font-medium">In stock</th>
                    <th scope="col" className="px-4 py-3 text-right font-medium">Safety</th>
                    <th scope="col" className="px-4 py-3 text-right font-medium">Reorder pt</th>
                    <th scope="col" className="px-4 py-3 text-right font-medium">Lead time</th>
                    <th scope="col" className="px-4 py-3 text-right font-medium">Cover</th>
                    <th scope="col" className="px-4 py-3 font-medium">Risk</th>
                    <th scope="col" className="px-4 py-3 font-medium">
                      <span className="sr-only">Actions</span>
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {!data &&
                    Array.from({ length: 6 }, (_, i) => (
                      <tr key={i}>
                        <td colSpan={10} className="px-4 py-3">
                          <Skeleton className="h-8 w-full" />
                        </td>
                      </tr>
                    ))}
                  {rows.map((item) => (
                    <tr key={item.product_id} className="transition-colors hover:bg-muted/40">
                      <td className="px-4 py-3">
                        <div className="flex flex-col">
                          <span className="font-mono text-sm font-medium">{item.product_id}</span>
                          <span className="max-w-56 truncate text-xs text-muted-foreground">{item.description}</span>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <SupplierChip id={item.supplier_id} />
                      </td>
                      <td className="px-4 py-3">
                        <StockGauge item={item} />
                      </td>
                      <td className="px-4 py-3 text-right font-medium tabular-nums">{item.current_stock.toLocaleString()}</td>
                      <td className="px-4 py-3 text-right tabular-nums text-muted-foreground">{item.safety_stock.toLocaleString()}</td>
                      <td className="px-4 py-3 text-right tabular-nums text-muted-foreground">{item.reorder_point.toLocaleString()}</td>
                      <td className="px-4 py-3 text-right tabular-nums text-muted-foreground">{item.lead_time_days} d</td>
                      <td className="px-4 py-3 text-right tabular-nums">
                        <span className={cn('font-medium', item.days_of_cover < item.lead_time_days && 'text-risk-critical')}>
                          {item.days_of_cover.toFixed(1)} d
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <RiskBadge level={item.risk_level} />
                      </td>
                      <td className="px-4 py-3 text-right">
                        <Link
                          href={`/forecasts?product=${encodeURIComponent(item.product_id)}`}
                          className="inline-flex h-8 items-center gap-1.5 rounded-lg border bg-background px-2.5 text-xs font-medium transition-colors hover:bg-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
                        >
                          <LineChart className="size-3.5" aria-hidden="true" />
                          Forecast
                          <span className="sr-only"> for {item.product_id}</span>
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {data && rows.length === 0 && (
              <div className="flex flex-col items-center gap-2 px-4 py-12 text-center text-sm text-muted-foreground">
                <PackageSearch className="size-6" aria-hidden="true" />
                No SKUs match this filter.
              </div>
            )}

            {data && (
              <div className="flex flex-wrap items-center justify-between gap-3 border-t bg-muted/20 px-4 py-3 text-xs text-muted-foreground">
                <span>
                  Showing {rows.length.toLocaleString()} of {data.length.toLocaleString()} SKUs
                </span>
                <span className="flex items-center gap-4">
                  <span className="flex items-center gap-1.5">
                    <span className="h-3 w-px bg-foreground/40" aria-hidden="true" />
                    Safety stock
                  </span>
                  <span className="flex items-center gap-1.5">
                    <span className="h-3 w-0.5 rounded-full bg-foreground/70" aria-hidden="true" />
                    Reorder point
                  </span>
                </span>
              </div>
            )}
          </Panel>
        </>
      )}
    </>
  )
}
