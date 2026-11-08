'use client'

import { useId } from 'react'
import {
  Area,
  CartesianGrid,
  ComposedChart,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { ForecastPoint } from '@/lib/types'

const dateFormat = new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric' })

function formatDate(value: unknown) {
  const date = new Date(`${String(value)}T00:00:00`)
  return Number.isNaN(date.getTime()) ? String(value) : dateFormat.format(date)
}

interface TooltipProps {
  active?: boolean
  label?: unknown
  payload?: ReadonlyArray<{ dataKey?: unknown; value?: unknown }>
}

function ChartTooltip({ active, label, payload }: TooltipProps) {
  if (!active || !payload?.length) return null
  const rows = payload.filter((item) => typeof item.value === 'number')
  if (!rows.length) return null

  return (
    <div className="min-w-36 rounded-lg border bg-popover px-3 py-2 text-xs text-popover-foreground shadow-md">
      <p className="mb-1.5 font-medium">{formatDate(label)}</p>
      <ul className="flex flex-col gap-1">
        {rows.map((item) => {
          const isForecast = item.dataKey === 'forecast'
          return (
            <li key={String(item.dataKey)} className="flex items-center justify-between gap-4">
              <span className="flex items-center gap-2 text-muted-foreground">
                <span
                  className="size-2 rounded-full"
                  style={{ background: isForecast ? 'var(--primary)' : 'var(--muted-foreground)' }}
                />
                {isForecast ? 'Forecast' : 'Actual'}
              </span>
              <span className="font-medium tabular-nums">{Number(item.value).toLocaleString()}</span>
            </li>
          )
        })}
      </ul>
    </div>
  )
}

export function ForecastChart({ series, today }: { series: ForecastPoint[]; today: string }) {
  const gradientId = useId().replace(/:/g, '')
  const lastDate = series.at(-1)?.date

  return (
    <div
      role="img"
      aria-label="Line chart comparing actual daily demand with the model forecast"
      className="h-80 w-full"
    >
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={series} margin={{ top: 8, right: 8, bottom: 0, left: -12 }}>
          <defs>
            <linearGradient id={`${gradientId}-actual`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--muted-foreground)" stopOpacity={0.28} />
              <stop offset="100%" stopColor="var(--muted-foreground)" stopOpacity={0} />
            </linearGradient>
            <linearGradient id={`${gradientId}-forecast`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--primary)" stopOpacity={0.38} />
              <stop offset="100%" stopColor="var(--primary)" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid vertical={false} stroke="var(--border)" strokeDasharray="3 3" />
          <XAxis
            dataKey="date"
            tickFormatter={formatDate}
            tickLine={false}
            axisLine={false}
            tick={{ fill: 'var(--muted-foreground)', fontSize: 12 }}
            minTickGap={32}
            tickMargin={8}
          />
          <YAxis
            tickLine={false}
            axisLine={false}
            tick={{ fill: 'var(--muted-foreground)', fontSize: 12 }}
            width={52}
          />
          <Tooltip
            content={ChartTooltip}
            cursor={{ stroke: 'var(--muted-foreground)', strokeDasharray: '3 3' }}
          />
          {lastDate && (
            <ReferenceArea x1={today} x2={lastDate} fill="var(--primary)" fillOpacity={0.05} stroke="none" />
          )}
          <ReferenceLine
            x={today}
            stroke="var(--muted-foreground)"
            strokeDasharray="4 4"
            label={{ value: 'Today', position: 'insideTopLeft', fill: 'var(--muted-foreground)', fontSize: 12 }}
          />
          <Area
            type="monotone"
            dataKey="actual"
            stroke="var(--muted-foreground)"
            strokeWidth={2}
            fill={`url(#${gradientId}-actual)`}
            dot={false}
            activeDot={{ r: 4 }}
            connectNulls={false}
            isAnimationActive={false}
          />
          <Area
            type="monotone"
            dataKey="forecast"
            stroke="var(--primary)"
            strokeWidth={2.5}
            strokeDasharray="6 4"
            fill={`url(#${gradientId}-forecast)`}
            dot={false}
            activeDot={{ r: 4 }}
            connectNulls={false}
            isAnimationActive={false}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}
