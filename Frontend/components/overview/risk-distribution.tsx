'use client'

import { Cell, Pie, PieChart, ResponsiveContainer } from 'recharts'
import type { RiskLevel } from '@/lib/types'
import { cn } from '@/lib/utils'
import { RISK_LEVELS, riskColor, riskStyles } from '@/components/risk-badge'

export function RiskDistribution({ distribution }: { distribution: Record<RiskLevel, number> }) {
  const total = RISK_LEVELS.reduce((sum, level) => sum + distribution[level], 0)
  const chartData =
    total > 0
      ? RISK_LEVELS.map((level) => ({ level, value: distribution[level], fill: riskColor[level] }))
      : [{ level: 'NONE', value: 1, fill: 'var(--muted)' }]

  return (
    <div className="mt-6 flex flex-col gap-6">
      <div
        role="img"
        aria-label={RISK_LEVELS.map((level) => `${distribution[level]} ${level.toLowerCase()}`).join(', ')}
        className="relative mx-auto size-48"
      >
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={chartData}
              dataKey="value"
              nameKey="level"
              innerRadius="70%"
              outerRadius="100%"
              startAngle={90}
              endAngle={-270}
              paddingAngle={total > 0 ? 3 : 0}
              cornerRadius={5}
              stroke="none"
              isAnimationActive={false}
            >
              {chartData.map((entry) => (
                <Cell key={entry.level} fill={entry.fill} />
              ))}
            </Pie>
          </PieChart>
        </ResponsiveContainer>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-3xl font-semibold tabular-nums tracking-tight">{total.toLocaleString()}</span>
          <span className="text-xs text-muted-foreground">active SKUs</span>
        </div>
      </div>

      <ul className="flex flex-col gap-3">
        {RISK_LEVELS.map((level) => {
          const share = total ? (distribution[level] / total) * 100 : 0
          return (
            <li key={level} className="flex flex-col gap-1.5">
              <div className="flex items-center justify-between text-sm">
                <span className="flex items-center gap-2">
                  <span className={cn('size-2.5 rounded-full', riskStyles[level].dot)} aria-hidden="true" />
                  {level.charAt(0) + level.slice(1).toLowerCase()}
                </span>
                <span className="tabular-nums text-muted-foreground">
                  <span className="font-medium text-foreground">{distribution[level].toLocaleString()}</span>
                  {' · '}
                  {Math.round(share)}%
                </span>
              </div>
              <div className="h-1 overflow-hidden rounded-full bg-muted" aria-hidden="true">
                <div
                  className={cn('h-full rounded-full transition-[width] duration-700', riskStyles[level].bar)}
                  style={{ width: `${share}%` }}
                />
              </div>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
