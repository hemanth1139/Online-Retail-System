'use client'

import { useId, useState } from 'react'
import { Cpu, Package, Ruler, Sigma, Target, ChevronDown } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { useForecast, useProductOptions } from '@/lib/api'
import type { ForecastHorizon } from '@/lib/types'
import { cn } from '@/lib/utils'
import { ErrorState, Panel, Skeleton } from '@/components/data-state'
import { ForecastChart } from '@/components/forecasts/forecast-chart'
import { Meter } from '@/components/meter'
import { PageHeader } from '@/components/page-header'
import { Segmented } from '@/components/segmented'

const HORIZON_OPTIONS = [
  { value: 7 as ForecastHorizon, label: '7 days' },
  { value: 30 as ForecastHorizon, label: '30 days' },
]

function Stat({
  label,
  value,
  hint,
  icon: Icon,
  meter,
  delay,
}: {
  label: string
  value: string
  hint: string
  icon: LucideIcon
  meter?: number
  delay: number
}) {
  return (
    <Panel className="animate-rise flex flex-col gap-3 p-4" style={{ animationDelay: `${delay}ms` }}>
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-medium text-muted-foreground">{label}</h3>
        <span className="flex size-8 items-center justify-center rounded-lg bg-primary/10 text-primary">
          <Icon className="size-4" aria-hidden="true" />
        </span>
      </div>
      <div>
        <p className="text-2xl font-semibold tabular-nums tracking-tight">{value}</p>
        <p className="mt-1 text-xs text-muted-foreground">{hint}</p>
      </div>
      {meter !== undefined && <Meter value={meter} label="Forecast accuracy, 100 minus WAPE" />}
    </Panel>
  )
}

function Legend() {
  return (
    <ul className="flex items-center gap-4 text-xs text-muted-foreground">
      <li className="flex items-center gap-2">
        <span className="h-0.5 w-5 rounded-full bg-muted-foreground" aria-hidden="true" />
        Actual
      </li>
      <li className="flex items-center gap-2">
        <span
          className="h-0.5 w-5 rounded-full bg-[repeating-linear-gradient(90deg,var(--primary)_0_6px,transparent_6px_9px)]"
          aria-hidden="true"
        />
        Forecast
      </li>
    </ul>
  )
}

export function ForecastsView({ initialProduct }: { initialProduct?: string | null }) {
  const selectId = useId()
  const [selectedProduct, setSelectedProduct] = useState<string | null>(initialProduct ?? null)
  const [horizon, setHorizon] = useState<ForecastHorizon>(30)

  const { data: products, error: productsError } = useProductOptions()
  const productId = selectedProduct ?? products?.[0]?.product_id ?? null
  const { data: forecast, error: forecastError, isLoading } = useForecast(productId, horizon)
  const error = productsError ?? forecastError

  return (
    <>
      <PageHeader
        title="Demand Forecasts"
        description="Compare recent actuals with the model forecast for any SKU."
      />

      {error ? (
        <ErrorState error={error} message="Unable to load forecast data." />
      ) : (
        <>
          <Panel className="flex flex-col gap-4 p-4 sm:flex-row sm:items-end sm:justify-between">
            <div className="flex flex-1 flex-col gap-1.5 sm:max-w-md">
              <label htmlFor={selectId} className="text-sm font-medium">
                Product
              </label>
              <div className="relative">
                <select
                  id={selectId}
                  value={productId ?? ''}
                  onChange={(event) => setSelectedProduct(event.target.value)}
                  disabled={!products}
                  className="h-10 w-full appearance-none rounded-lg border bg-background pr-9 pl-3 text-sm focus-visible:outline-2 focus-visible:outline-ring disabled:opacity-60"
                >
                  {products?.map((product) => (
                    <option key={product.product_id} value={product.product_id}>
                      {product.product_id} · {product.description}
                    </option>
                  ))}
                </select>
                <ChevronDown
                  className="pointer-events-none absolute top-1/2 right-3 size-4 -translate-y-1/2 text-muted-foreground"
                  aria-hidden="true"
                />
              </div>
            </div>
            <div className="flex flex-col gap-1.5">
              <span className="text-sm font-medium" aria-hidden="true">
                Horizon
              </span>
              <Segmented legend="Forecast horizon" options={HORIZON_OPTIONS} value={horizon} onChange={setHorizon} />
            </div>
          </Panel>

          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            {forecast ? (
              <>
                <Stat
                  label={`Projected ${forecast.horizon_days}-day demand`}
                  value={`${forecast.projected_total.toLocaleString()} units`}
                  hint={`≈ ${Math.round(forecast.projected_total / forecast.horizon_days).toLocaleString()} units per day`}
                  icon={Package}
                  delay={0}
                />
                <Stat
                  label="MAE"
                  value={forecast.metrics.mae.toFixed(1)}
                  hint="Mean absolute error"
                  icon={Ruler}
                  delay={60}
                />
                <Stat
                  label="RMSE"
                  value={forecast.metrics.rmse.toFixed(1)}
                  hint="Root mean squared error"
                  icon={Sigma}
                  delay={120}
                />
                <Stat
                  label="WAPE"
                  value={`${forecast.metrics.wape.toFixed(1)}%`}
                  hint={`${Math.max(0, 100 - forecast.metrics.wape).toFixed(1)}% accuracy`}
                  icon={Target}
                  meter={Math.max(0, 100 - forecast.metrics.wape)}
                  delay={180}
                />
              </>
            ) : (
              Array.from({ length: 4 }, (_, i) => (
                <Panel key={i} className="p-4">
                  <Skeleton className="h-3 w-20" />
                  <Skeleton className="mt-4 h-7 w-24" />
                  <Skeleton className="mt-2 h-3 w-28" />
                </Panel>
              ))
            )}
          </div>

          <Panel
            className={cn('animate-rise p-5 transition-opacity', isLoading && 'opacity-60')}
            style={{ animationDelay: '240ms' }}
          >
            <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div className="min-w-0">
                <h2 className="text-base font-semibold">Actual vs. forecast</h2>
                <p className="mt-1 truncate text-sm text-muted-foreground">
                  {forecast ? (
                    <>
                      <span className="font-mono text-foreground">{forecast.product_id}</span> · {forecast.description}
                    </>
                  ) : (
                    'Units per day'
                  )}
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-3">
                <Legend />
                {forecast && (
                  <span className="inline-flex items-center gap-1.5 rounded-full border bg-background px-2.5 py-1 text-xs text-muted-foreground">
                    <Cpu className="size-3" aria-hidden="true" />
                    Model {forecast.model_version}
                  </span>
                )}
              </div>
            </div>
            {forecast ? (
              <ForecastChart series={forecast.series} today={forecast.today} />
            ) : (
              <Skeleton className="h-80 w-full" />
            )}
          </Panel>
        </>
      )}
    </>
  )
}
