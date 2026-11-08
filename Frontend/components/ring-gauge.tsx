import { cn } from '@/lib/utils'

export function RingGauge({
  value,
  label,
  size = 120,
  stroke = 10,
  className,
  children,
}: {
  value: number
  label: string
  size?: number
  stroke?: number
  className?: string
  children?: React.ReactNode
}) {
  const percent = Math.max(0, Math.min(100, value))
  const radius = (size - stroke) / 2
  const circumference = 2 * Math.PI * radius

  return (
    <div
      role="img"
      aria-label={label}
      className={cn('relative shrink-0 text-primary', className)}
      style={{ width: size, height: size }}
    >
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90" aria-hidden="true">
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" strokeWidth={stroke} className="stroke-muted" />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          strokeWidth={stroke}
          strokeLinecap="round"
          stroke="currentColor"
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - percent / 100)}
          className="transition-[stroke-dashoffset] duration-1000"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center text-foreground">
        {children}
      </div>
    </div>
  )
}
