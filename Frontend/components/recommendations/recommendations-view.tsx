'use client'

import { useMemo, useState } from 'react'
import { ClipboardCheck, PackagePlus, Truck } from 'lucide-react'
import { useRecommendations } from '@/lib/api'
import type { OrderStatus } from '@/lib/types'
import { ErrorState, Panel, Skeleton } from '@/components/data-state'
import { CreatePoButton } from '@/components/create-po-button'
import { MetricCard, MetricCardSkeleton } from '@/components/metric-card'
import { Meter } from '@/components/meter'
import { PageHeader } from '@/components/page-header'
import { RiskBadge, riskStyles } from '@/components/risk-badge'
import { Segmented } from '@/components/segmented'
import { SupplierChip } from '@/components/supplier-chip'

type Filter = OrderStatus | 'All'

const FILTER_OPTIONS: { value: Filter; label: string }[] = [
  { value: 'All', label: 'All' },
  { value: 'Pending', label: 'Pending' },
  { value: 'Ordered', label: 'Ordered' },
]

export function RecommendationsView() {
  const { data, error } = useRecommendations()
  const [filter, setFilter] = useState<Filter>('Pending')

  const pending = useMemo(() => (data ?? []).filter((item) => item.status === 'Pending'), [data])
  const rows = useMemo(
    () => (data ?? []).filter((item) => filter === 'All' || item.status === filter),
    [data, filter],
  )
  const visibleUnits = rows.reduce((sum, item) => sum + item.suggested_reorder_qty, 0)

  return (
    <>
      <PageHeader
        title="Purchase Recommendations"
        description="Suggested reorder quantities that cover expected demand over each supplier's lead time."
      />

      {error ? (
        <ErrorState error={error} message="Unable to load recommendations." />
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-3">
            {data ? (
              <>
                <MetricCard
                  label="Pending orders"
                  value={pending.length.toLocaleString()}
                  hint={`${(data.length - pending.length).toLocaleString()} already ordered`}
                  icon={ClipboardCheck}
                  tone={pending.length > 0 ? 'danger' : 'default'}
                  delay={0}
                />
                <MetricCard
                  label="Units to order"
                  value={pending.reduce((sum, item) => sum + item.suggested_reorder_qty, 0).toLocaleString()}
                  hint="Across all pending orders"
                  icon={PackagePlus}
                  delay={60}
                />
                <MetricCard
                  label="Suppliers involved"
                  value={new Set(pending.map((item) => item.supplier_id)).size.toLocaleString()}
                  hint="With at least one pending order"
                  icon={Truck}
                  delay={120}
                />
              </>
            ) : (
              Array.from({ length: 3 }, (_, i) => <MetricCardSkeleton key={i} />)
            )}
          </div>

          <div className="flex items-center justify-between gap-3">
            <Segmented legend="Order status" options={FILTER_OPTIONS} value={filter} onChange={setFilter} />
            {data && (
              <p className="text-sm text-muted-foreground">
                {rows.length.toLocaleString()} {rows.length === 1 ? 'recommendation' : 'recommendations'}
              </p>
            )}
          </div>

          <Panel className="animate-rise overflow-hidden" style={{ animationDelay: '180ms' }}>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[56rem] text-sm">
                <caption className="sr-only">Suggested purchase orders by product</caption>
                <thead>
                  <tr className="border-b bg-muted/40 text-left text-xs uppercase tracking-wide text-muted-foreground">
                    <th scope="col" className="px-4 py-3 font-medium">Product</th>
                    <th scope="col" className="px-4 py-3 font-medium">Supplier</th>
                    <th scope="col" className="px-4 py-3 font-medium">Coverage</th>
                    <th scope="col" className="px-4 py-3 text-right font-medium">Lead-time demand</th>
                    <th scope="col" className="px-4 py-3 text-right font-medium">Suggested qty</th>
                    <th scope="col" className="px-4 py-3 font-medium">Risk</th>
                    <th scope="col" className="px-4 py-3 text-right font-medium">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {!data &&
                    Array.from({ length: 6 }, (_, i) => (
                      <tr key={i}>
                        <td colSpan={7} className="px-4 py-3">
                          <Skeleton className="h-8 w-full" />
                        </td>
                      </tr>
                    ))}
                  {rows.map((item) => {
                    const coverage =
                      item.expected_lead_time_demand > 0
                        ? (item.current_stock / item.expected_lead_time_demand) * 100
                        : 100
                    const moqMultiple = item.supplier_moq > 0 ? item.suggested_reorder_qty / item.supplier_moq : 0

                    return (
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
                          <div className="flex w-40 flex-col gap-1.5">
                            <Meter
                              value={coverage}
                              label={`Stock covers ${Math.round(coverage)} percent of lead-time demand`}
                              barClassName={riskStyles[item.risk_level].bar}
                            />
                            <span className="text-xs tabular-nums text-muted-foreground">
                              {item.current_stock.toLocaleString()} in stock · {Math.round(coverage)}%
                            </span>
                          </div>
                        </td>
                        <td className="px-4 py-3 text-right tabular-nums text-muted-foreground">
                          {item.expected_lead_time_demand.toLocaleString()}
                        </td>
                        <td className="px-4 py-3 text-right">
                          <span className="inline-flex flex-col items-end">
                            <span className="rounded-md bg-primary/10 px-2 py-0.5 text-sm font-semibold tabular-nums text-primary">
                              {item.suggested_reorder_qty.toLocaleString()}
                            </span>
                            {moqMultiple > 0 && (
                              <span className="mt-1 text-xs tabular-nums text-muted-foreground">
                                {Number.isInteger(moqMultiple) ? moqMultiple : moqMultiple.toFixed(1)}× MOQ of{' '}
                                {item.supplier_moq.toLocaleString()}
                              </span>
                            )}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <RiskBadge level={item.risk_level} />
                        </td>
                        <td className="px-4 py-3 text-right">
                          <CreatePoButton recommendation={item} size="sm" />
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
                {data && rows.length > 0 && (
                  <tfoot>
                    <tr className="border-t bg-muted/20 text-sm">
                      <th scope="row" colSpan={4} className="px-4 py-3 text-left font-medium text-muted-foreground">
                        Total suggested
                      </th>
                      <td className="px-4 py-3 text-right font-semibold tabular-nums">
                        {visibleUnits.toLocaleString()}
                      </td>
                      <td colSpan={2} />
                    </tr>
                  </tfoot>
                )}
              </table>
            </div>

            {data && rows.length === 0 && (
              <p className="px-4 py-12 text-center text-sm text-muted-foreground">
                No recommendations in this view.
              </p>
            )}
          </Panel>
        </>
      )}
    </>
  )
}
