import type { Metadata } from 'next'
import { ForecastsView } from '@/components/forecasts/forecasts-view'

export const metadata: Metadata = { title: 'Demand Forecasts | Replenish' }

export default async function ForecastsPage({
  searchParams,
}: {
  searchParams: Promise<{ product?: string }>
}) {
  const { product } = await searchParams
  return <ForecastsView initialProduct={product ?? null} />
}
