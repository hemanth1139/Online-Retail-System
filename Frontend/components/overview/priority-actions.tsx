import type { Recommendation } from '@/lib/types'
import { CreatePoButton } from '@/components/create-po-button'
import { Meter } from '@/components/meter'
import { RiskBadge, riskStyles } from '@/components/risk-badge'
import { SupplierChip } from '@/components/supplier-chip'

export function PriorityActions({ actions }: { actions: Recommendation[] }) {
  if (actions.length === 0) {
    return (
      <p className="mt-6 rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">
        Nothing urgent. All SKUs are comfortably stocked.
      </p>
    )
  }

  return (
    <ol className="mt-4 flex flex-col gap-3">
      {actions.map((action, index) => {
        const coverage =
          action.expected_lead_time_demand > 0
            ? (action.current_stock / action.expected_lead_time_demand) * 100
            : 100

        return (
          <li
            key={action.product_id}
            className="flex flex-col gap-4 rounded-lg border bg-background/50 p-4 transition-colors hover:bg-muted/40 sm:flex-row sm:items-center"
          >
            <span
              className="flex size-8 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-semibold tabular-nums text-muted-foreground"
              aria-hidden="true"
            >
              {index + 1}
            </span>
            <div className="flex min-w-0 flex-1 flex-col gap-2">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-sm font-medium">{action.product_id}</span>
                <RiskBadge level={action.risk_level} />
                <SupplierChip id={action.supplier_id} />
              </div>
              <p className="truncate text-sm text-muted-foreground">{action.description}</p>
              <div className="flex items-center gap-3">
                <Meter
                  value={coverage}
                  label={`Stock covers ${Math.round(coverage)} percent of lead-time demand`}
                  barClassName={riskStyles[action.risk_level].bar}
                  className="max-w-48"
                />
                <span className="text-xs tabular-nums text-muted-foreground">
                  {action.current_stock.toLocaleString()} in stock · {Math.round(coverage)}% of lead-time demand
                </span>
              </div>
            </div>
            <div className="flex items-center justify-between gap-4 sm:flex-col sm:items-end sm:justify-center">
              <div className="text-left sm:text-right">
                <p className="text-lg font-semibold tabular-nums leading-none">
                  {action.suggested_reorder_qty.toLocaleString()}
                </p>
                <p className="mt-1 text-xs text-muted-foreground">units to order</p>
              </div>
              <CreatePoButton recommendation={action} size="sm" />
            </div>
          </li>
        )
      })}
    </ol>
  )
}
