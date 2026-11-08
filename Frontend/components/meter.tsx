import { cn } from '@/lib/utils'

export function Meter({
  value,
  label,
  className,
  barClassName,
}: {
  value: number
  label: string
  className?: string
  barClassName?: string
}) {
  const percent = Math.max(0, Math.min(100, value))

  return (
    <div
      role="meter"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(percent)}
      className={cn('h-1.5 w-full overflow-hidden rounded-full bg-muted', className)}
    >
      <div
        className={cn('h-full rounded-full bg-primary transition-[width] duration-700', barClassName)}
        style={{ width: `${percent}%` }}
      />
    </div>
  )
}
