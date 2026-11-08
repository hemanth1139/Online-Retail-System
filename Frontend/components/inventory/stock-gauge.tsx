import type { InventoryItem } from '@/lib/types'
import { cn } from '@/lib/utils'
import { riskStyles } from '@/components/risk-badge'

export function StockGauge({ item }: { item: InventoryItem }) {
  const scale = Math.max(item.current_stock, item.reorder_point * 1.5, 1)
  const percent = (value: number) => `${Math.min(100, (value / scale) * 100)}%`

  return (
    <div
      role="img"
      aria-label={`${item.current_stock} in stock, safety stock ${item.safety_stock}, reorder point ${item.reorder_point}`}
      className="relative h-2 w-36 rounded-full bg-muted"
    >
      <div
        className={cn('h-full rounded-full', riskStyles[item.risk_level].bar)}
        style={{ width: percent(item.current_stock) }}
      />
      <span
        className="absolute -top-1 -bottom-1 w-px bg-foreground/40"
        style={{ left: percent(item.safety_stock) }}
        aria-hidden="true"
      />
      <span
        className="absolute -top-1 -bottom-1 w-0.5 rounded-full bg-foreground/70"
        style={{ left: percent(item.reorder_point) }}
        aria-hidden="true"
      />
    </div>
  )
}
