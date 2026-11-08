export type RiskLevel = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW'
export type OrderStatus = 'Pending' | 'Ordered'
export type ForecastHorizon = 7 | 30

export interface InventoryItem {
  product_id: string
  description: string
  supplier_id: string
  current_stock: number
  safety_stock: number
  reorder_point: number
  lead_time_days: number
  avg_daily_demand: number
  days_of_cover: number
  risk_level: RiskLevel
}

export interface Recommendation {
  product_id: string
  description: string
  supplier_id: string
  current_stock: number
  expected_lead_time_demand: number
  suggested_reorder_qty: number
  supplier_moq: number
  risk_level: RiskLevel
  status: OrderStatus
}

export interface DashboardSummary {
  total_active_skus: number
  critical_high_count: number
  projected_30d_demand: number
  forecast_accuracy: { wape: number; mae: number }
  risk_distribution: Record<RiskLevel, number>
  priority_actions: Recommendation[]
}

export interface ForecastPoint {
  date: string
  actual: number | null
  forecast: number | null
}

export interface ForecastResponse {
  product_id: string
  description: string
  horizon_days: ForecastHorizon
  model_version: string
  metrics: { mae: number; rmse: number; wape: number }
  projected_total: number
  today: string
  series: ForecastPoint[]
}

export interface ProductOption {
  product_id: string
  description: string
}
