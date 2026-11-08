export function PageHeader({
  title,
  description,
  children,
}: {
  title: string
  description: string
  children?: React.ReactNode
}) {
  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div className="flex flex-col gap-1">
        <h1 className="text-balance text-2xl font-semibold tracking-tight">{title}</h1>
        <p className="text-pretty text-sm text-muted-foreground">{description}</p>
      </div>
      {children}
    </div>
  )
}
