'use client'

import { Check, Loader2, ShoppingCart } from 'lucide-react'
import { toast } from 'sonner'
import { usePurchaseOrders } from '@/lib/api'
import type { Recommendation } from '@/lib/types'
import { cn } from '@/lib/utils'

export function CreatePoButton({
  recommendation,
  size = 'md',
}: {
  recommendation: Pick<Recommendation, 'product_id' | 'supplier_id' | 'suggested_reorder_qty' | 'status'>
  size?: 'sm' | 'md'
}) {
  const { createPurchaseOrder, submitting } = usePurchaseOrders()
  const { product_id, supplier_id, suggested_reorder_qty, status } = recommendation
  const isSubmitting = submitting.has(product_id)

  async function handleClick() {
    try {
      await createPurchaseOrder(product_id)
      toast.success('Purchase order created', {
        description: `${suggested_reorder_qty.toLocaleString()} units of ${product_id} ordered from ${supplier_id}.`,
      })
    } catch {
      toast.error('Could not create purchase order', {
        description: 'Please try again in a moment.',
      })
    }
  }

  const sizing = size === 'sm' ? 'h-8 px-2.5 text-xs' : 'h-9 px-3 text-sm'

  if (status === 'Ordered') {
    return (
      <span
        className={cn(
          'inline-flex items-center gap-1.5 font-medium text-risk-low',
          size === 'sm' ? 'text-xs' : 'text-sm',
        )}
      >
        <Check className="size-4" aria-hidden="true" />
        PO created
      </span>
    )
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={isSubmitting}
      className={cn(
        'inline-flex shrink-0 items-center whitespace-nowrap justify-center gap-1.5 rounded-lg bg-primary font-medium text-primary-foreground transition-opacity hover:opacity-90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring disabled:cursor-not-allowed disabled:opacity-60',
        sizing,
      )}
    >
      {isSubmitting ? (
        <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
      ) : (
        <ShoppingCart className="size-3.5" aria-hidden="true" />
      )}
      Create PO
      <span className="sr-only"> for {product_id}</span>
    </button>
  )
}
