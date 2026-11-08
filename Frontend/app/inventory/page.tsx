import type { Metadata } from 'next'
import { InventoryView } from '@/components/inventory/inventory-view'

export const metadata: Metadata = { title: 'Inventory & Risks | Replenish' }

export default function InventoryPage() {
  return <InventoryView />
}
