'use client'

import { useId } from 'react'
import { cn } from '@/lib/utils'

export function Segmented<T extends string | number>({
  legend,
  options,
  value,
  onChange,
  className,
}: {
  legend: string
  options: { value: T; label: string }[]
  value: T
  onChange: (value: T) => void
  className?: string
}) {
  const name = useId()

  return (
    <fieldset className={className}>
      <legend className="sr-only">{legend}</legend>
      <div className="inline-flex rounded-lg border bg-muted/50 p-0.5">
        {options.map((option) => (
          <label
            key={String(option.value)}
            className={cn(
              'cursor-pointer rounded-md px-3 py-1.5 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-ring',
              value === option.value && 'bg-card text-foreground shadow-xs ring-1 ring-border',
            )}
          >
            <input
              type="radio"
              name={name}
              value={String(option.value)}
              checked={value === option.value}
              onChange={() => onChange(option.value)}
              className="sr-only"
            />
            {option.label}
          </label>
        ))}
      </div>
    </fieldset>
  )
}
