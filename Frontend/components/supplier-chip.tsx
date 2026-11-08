import { Truck } from 'lucide-react'

export function SupplierChip({ id }: { id: string }) {
  return (
    <span className="inline-flex items-center gap-2 whitespace-nowrap">
      <span className="flex size-6 items-center justify-center rounded-md bg-muted text-muted-foreground">
        <Truck className="size-3.5" aria-hidden="true" />
      </span>
      <span className="font-mono text-xs">{id}</span>
    </span>
  )
}
