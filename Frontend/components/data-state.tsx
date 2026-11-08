import { AlertCircle, PlugZap } from 'lucide-react'
import { ApiNotConfiguredError } from '@/lib/api-errors'
import { cn } from '@/lib/utils'

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn('animate-pulse rounded-md bg-muted', className)} />
}

const EXPECTED_ENDPOINTS = [
  { method: 'GET', path: '/api/dashboard/summary' },
  { method: 'GET', path: '/api/forecasts/{product_id}?horizon=7|30' },
  { method: 'GET', path: '/api/inventory/risks' },
  { method: 'GET', path: '/api/products' },
  { method: 'GET', path: '/api/recommendations' },
  { method: 'POST', path: '/api/recommendations/{product_id}/purchase-order' },
]

function ApiNotConnected() {
  return (
    <section
      role="alert"
      className="flex flex-col gap-5 rounded-xl border border-dashed bg-card p-6 shadow-xs sm:p-8"
    >
      <div className="flex items-start gap-4">
        <span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
          <PlugZap className="size-5" aria-hidden="true" />
        </span>
        <div className="flex flex-col gap-1">
          <h2 className="text-base font-semibold">Connect your forecasting API</h2>
          <p className="text-pretty text-sm text-muted-foreground">
            This dashboard has no built-in data. Set the{' '}
            <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-xs text-foreground">
              API_BASE_URL
            </code>{' '}
            environment variable to your FastAPI service (for example https://forecast.example.com) and
            every page will load live data from it.
          </p>
        </div>
      </div>
      <ul className="flex flex-col divide-y rounded-lg border bg-background text-sm">
        {EXPECTED_ENDPOINTS.map(({ method, path }) => (
          <li key={`${method}${path}`} className="flex items-center gap-3 px-3 py-2">
            <span
              className={cn(
                'w-12 shrink-0 rounded px-1.5 py-0.5 text-center font-mono text-[11px] font-semibold',
                method === 'GET' ? 'bg-muted text-muted-foreground' : 'bg-primary/10 text-primary',
              )}
            >
              {method}
            </span>
            <code className="min-w-0 truncate font-mono text-xs">{path}</code>
          </li>
        ))}
      </ul>
    </section>
  )
}

export function ErrorState({
  error,
  message = 'Unable to load data.',
}: {
  error?: unknown
  message?: string
}) {
  if (error instanceof ApiNotConfiguredError) return <ApiNotConnected />

  return (
    <div
      role="alert"
      className="flex items-center gap-2 rounded-xl border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive"
    >
      <AlertCircle className="size-4 shrink-0" aria-hidden="true" />
      {message}
    </div>
  )
}

export function Panel({
  className,
  children,
  style,
}: {
  className?: string
  children: React.ReactNode
  style?: React.CSSProperties
}) {
  return (
    <section
      style={style}
      className={cn('rounded-xl border bg-card text-card-foreground shadow-xs', className)}
    >
      {children}
    </section>
  )
}
