'use client'

import { useCallback, useState } from 'react'
import useSWR, { useSWRConfig } from 'swr'
import { ApiNotConfiguredError } from '@/lib/api-errors'
import type {
  DashboardSummary,
  ForecastHorizon,
  ForecastResponse,
  InventoryItem,
  ProductOption,
  Recommendation,
} from '@/lib/types'

/**
 * The browser always calls same-origin `/api/*`. next.config.mjs rewrites those calls to the
 * FastAPI service at `API_BASE_URL`, so no CORS setup is needed on the backend.
 */
const API_CONFIGURED = process.env.NEXT_PUBLIC_API_CONFIGURED === 'true'

export const endpoints = {
  summary: '/api/dashboard/summary',
  risks: '/api/inventory/risks',
  recommendations: '/api/recommendations',
  products: '/api/products',
  forecast: (productId: string, horizon: ForecastHorizon) =>
    `/api/forecasts/${encodeURIComponent(productId)}?horizon=${horizon}`,
  purchaseOrder: (productId: string) =>
    `/api/recommendations/${encodeURIComponent(productId)}/purchase-order`,
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  if (!API_CONFIGURED) throw new ApiNotConfiguredError()
  const response = await fetch(path, init)
  if (!response.ok) {
    throw new Error(`Request failed (${response.status})`)
  }
  return response.json() as Promise<T>
}

const fetcher = <T,>(path: string) => request<T>(path)

const swrOptions = {
  shouldRetryOnError: (error: unknown) => !(error instanceof ApiNotConfiguredError),
}

export function useDashboardSummary() {
  return useSWR<DashboardSummary>(endpoints.summary, fetcher, swrOptions)
}

export function useInventoryRisks() {
  return useSWR<InventoryItem[]>(endpoints.risks, fetcher, swrOptions)
}

export function useRecommendations() {
  return useSWR<Recommendation[]>(endpoints.recommendations, fetcher, swrOptions)
}

export function useProductOptions() {
  return useSWR<ProductOption[]>(endpoints.products, fetcher, swrOptions)
}

export function useForecast(productId: string | null, horizon: ForecastHorizon) {
  return useSWR<ForecastResponse>(
    productId ? endpoints.forecast(productId, horizon) : null,
    fetcher,
    { keepPreviousData: true, ...swrOptions },
  )
}

export function usePurchaseOrders() {
  const { mutate } = useSWRConfig()
  const [submitting, setSubmitting] = useState<ReadonlySet<string>>(new Set())

  const createPurchaseOrder = useCallback(
    async (productId: string) => {
      setSubmitting((prev) => new Set(prev).add(productId))
      try {
        const order = await request<Recommendation>(endpoints.purchaseOrder(productId), {
          method: 'POST',
        })
        await Promise.all([mutate(endpoints.recommendations), mutate(endpoints.summary)])
        return order
      } finally {
        setSubmitting((prev) => {
          const next = new Set(prev)
          next.delete(productId)
          return next
        })
      }
    },
    [mutate],
  )

  return { createPurchaseOrder, submitting }
}
