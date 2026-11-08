'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { Boxes, ClipboardList, Cpu, LayoutDashboard, TrendingUp, Warehouse } from 'lucide-react'
import { useDashboardSummary } from '@/lib/api'
import { cn } from '@/lib/utils'
import { ThemeToggle } from '@/components/theme-toggle'

const NAV_ITEMS = [
  { href: '/', label: 'Overview', icon: LayoutDashboard },
  { href: '/forecasts', label: 'Demand Forecasts', icon: TrendingUp },
  { href: '/inventory', label: 'Inventory & Risks', icon: Boxes },
  { href: '/recommendations', label: 'Purchase Recommendations', icon: ClipboardList },
]

function Brand() {
  return (
    <div className="flex items-center gap-2.5">
      <span className="flex size-9 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-xs">
        <Warehouse className="size-4.5" aria-hidden="true" />
      </span>
      <div className="flex flex-col leading-tight">
        <span className="text-sm font-semibold tracking-tight">Replenish</span>
        <span className="text-xs text-muted-foreground">Demand &amp; Inventory</span>
      </div>
    </div>
  )
}

function ApiStatus() {
  const { data, error } = useDashboardSummary()
  const state = data ? 'online' : error ? 'offline' : 'connecting'
  const label = { online: 'API connected', offline: 'API not connected', connecting: 'Connecting' }[state]

  return (
    <span
      role="status"
      className="inline-flex items-center gap-2 rounded-full border bg-card px-3 py-1 text-xs font-medium text-muted-foreground"
    >
      <span className="relative flex size-2">
        {state === 'online' && (
          <span className="absolute inline-flex size-full animate-ping rounded-full bg-risk-low opacity-60 motion-reduce:animate-none" />
        )}
        <span
          className={cn(
            'relative inline-flex size-2 rounded-full',
            state === 'online' && 'bg-risk-low',
            state === 'offline' && 'bg-risk-critical',
            state === 'connecting' && 'animate-pulse bg-muted-foreground',
          )}
        />
      </span>
      {label}
    </span>
  )
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const isActive = (href: string) => (href === '/' ? pathname === '/' : pathname.startsWith(href))
  const current = NAV_ITEMS.find((item) => isActive(item.href))

  return (
    <div className="min-h-dvh lg:grid lg:grid-cols-[17rem_1fr]">
      <aside className="sticky top-0 hidden h-dvh flex-col justify-between border-r bg-sidebar p-4 lg:flex">
        <div className="flex flex-col gap-8">
          <div className="px-2 pt-2">
            <Brand />
          </div>
          <div className="flex flex-col gap-2">
            <p className="px-3 text-xs font-medium uppercase tracking-wider text-muted-foreground">
              Workspace
            </p>
            <nav aria-label="Primary" className="flex flex-col gap-1">
              {NAV_ITEMS.map(({ href, label, icon: Icon }) => (
                <Link
                  key={href}
                  href={href}
                  aria-current={isActive(href) ? 'page' : undefined}
                  className={cn(
                    'group relative flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground',
                    isActive(href) && 'bg-sidebar-accent text-sidebar-accent-foreground',
                  )}
                >
                  {isActive(href) && (
                    <span className="absolute inset-y-2 -left-4 w-1 rounded-r-full bg-primary" aria-hidden="true" />
                  )}
                  <span
                    className={cn(
                      'flex size-7 items-center justify-center rounded-md transition-colors',
                      isActive(href)
                        ? 'bg-primary text-primary-foreground'
                        : 'bg-background/60 text-muted-foreground group-hover:text-foreground',
                    )}
                  >
                    <Icon className="size-3.5" aria-hidden="true" />
                  </span>
                  {label}
                </Link>
              ))}
            </nav>
          </div>
        </div>
        <div className="flex items-center gap-3 rounded-xl border bg-card p-3 shadow-xs">
          <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <Cpu className="size-4" aria-hidden="true" />
          </span>
          <div className="flex min-w-0 flex-col leading-tight">
            <span className="truncate text-sm font-medium">XGBoost forecaster</span>
            <span className="truncate text-xs text-muted-foreground">Daily SKU-level demand</span>
          </div>
        </div>
      </aside>

      <div className="relative flex min-w-0 flex-col">
        <div aria-hidden="true" className="bg-dot-grid pointer-events-none absolute inset-x-0 top-0 h-112" />

        <header className="sticky top-0 z-20 hidden h-14 items-center justify-between border-b bg-background/80 px-8 backdrop-blur lg:flex">
          <nav aria-label="Breadcrumb" className="flex items-center gap-2 text-sm text-muted-foreground">
            <span>Replenish</span>
            <span aria-hidden="true">/</span>
            <span className="font-medium text-foreground">{current?.label ?? 'Dashboard'}</span>
          </nav>
          <div className="flex items-center gap-3">
            <time
              suppressHydrationWarning
              dateTime={new Date().toISOString()}
              className="text-xs text-muted-foreground"
            >
              {new Date().toLocaleDateString('en-US', {
                weekday: 'short',
                month: 'short',
                day: 'numeric',
                year: 'numeric',
              })}
            </time>
            <ApiStatus />
            <ThemeToggle />
          </div>
        </header>

        <header className="sticky top-0 z-20 border-b bg-background/90 backdrop-blur lg:hidden">
          <div className="flex items-center justify-between px-4 py-3">
            <Brand />
            <ThemeToggle />
          </div>
          <nav aria-label="Primary" className="flex gap-1 overflow-x-auto px-4 pb-2">
            {NAV_ITEMS.map(({ href, label, icon: Icon }) => (
              <Link
                key={href}
                href={href}
                aria-current={isActive(href) ? 'page' : undefined}
                className={cn(
                  'flex shrink-0 items-center gap-2 rounded-lg px-3 py-1.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground',
                  isActive(href) && 'bg-accent text-foreground',
                )}
              >
                <Icon className="size-4" aria-hidden="true" />
                {label}
              </Link>
            ))}
          </nav>
        </header>

        <main className="relative mx-auto flex w-full max-w-6xl flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          {children}
        </main>
      </div>
    </div>
  )
}
