export type ResearchStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'

export interface ResearchTaskSummary {
  research_id: string
  research_name: string
  factor_name: string
  status: ResearchStatus
  progress: number
  started_at: string | null
  completed_at: string | null
  created_at: string | null
}

export interface ICAnalysisResult {
  ic_mean: number
  ic_std: number
  ic_ir: number
  ic_series: number[]
  ic_pvalue: number
  ic_positive_ratio: number
  ic_decay: Array<{ lag: number; ic: number }>
  sample_size: number
}

export interface QuantileAnalysisResult {
  quantile_count: number
  quantile_returns: number[]
  top_minus_bottom: number
  turnover_rate: number[]
  quantile_spread: number[]
  win_rate: number
  monotonicity: 'monotonic' | 'non_monotonic'
}

export interface StabilityAnalysisResult {
  stability_score: number
  period_consistency: Array<{ period: string; ic: number; rank_ic: number }>
  rank_ic: number
  ic_stability: number
}

export interface CorrelationAnalysisResult {
  correlation_matrix: number[][]
  mean_correlation: number
  max_correlation: number
  min_correlation: number
  orthogonality_score: number
  compared_factors: string[]
}

export interface ResearchSummary {
  factor_name: string
  overall_assessment: 'excellent' | 'good' | 'poor'
  key_findings: string[]
  next_steps: string[]
}

export interface ResearchTaskDetail extends ResearchTaskSummary {
  calculated_count: number
  total_stocks: number
  start_date: string | null
  end_date: string | null
  error_message: string | null
  result: {
    ic_analysis?: ICAnalysisResult
    quantile_analysis?: QuantileAnalysisResult
    stability_analysis?: StabilityAnalysisResult
    correlation_analysis?: CorrelationAnalysisResult
  } | null
  summary: ResearchSummary | null
  report: Record<string, any> | null
}

export interface ResearchTaskListResponse {
  recent_tasks: ResearchTaskSummary[]
  total_count: number
}

export interface CancelResearchResponse {
  success: boolean
  research_id: string
  status: string
  message: string
}
