// ─── Pagination ────────────────────────────────────────────────────────────────

export interface Pagination {
  page: number
  page_size: number
  total: number
  total_pages: number
}

export interface PagedResponse<T> {
  data: T[]
  pagination: Pagination
}

// ─── Core entities ────────────────────────────────────────────────────────────

export interface TeamBrief {
  id: number
  name: string
  short_name?: string
  logo_url?: string
}

export interface Team {
  id: number
  name: string
  short_name?: string
  logo_url?: string
  established_year?: number
  stadium_name?: string
  stadium_capacity?: number
}

export interface Season {
  id?: number
  name: string
}

// ─── Prediction types ──────────────────────────────────────────────────────────

export interface ProbabilityBreakdown {
  home_win: number
  draw: number
  away_win: number
}

export interface KeyFeatures {
  home_elo?: number
  away_elo?: number
  elo_diff?: number
  home_form5_ppg?: number
  away_form5_ppg?: number
  h2h_home_win_rate?: number
  home_season_ppg?: number
  away_season_ppg?: number
  home_absences?: number
  away_absences?: number
}

export type PredictRequest =
  | {
      match_id: number
      include_feature_breakdown?: boolean
    }
  | {
      home_team_id: number
      away_team_id: number
      match_datetime: string
      season_name: string
      match_week: number
      include_feature_breakdown?: boolean
    }

export interface PredictResponse {
  match_id?: number
  home_team_id: number
  away_team_id: number
  home_team_name: string
  away_team_name: string
  match_datetime?: string
  probabilities: ProbabilityBreakdown
  predicted_outcome: 'H' | 'D' | 'A'
  confidence: number          // float 0.0–1.0
  model_version: string
  key_features?: KeyFeatures
  feature_vector?: Record<string, number>
}

// ─── Match types ───────────────────────────────────────────────────────────────

export interface MatchListItem {
  id: number
  season_name: string
  match_datetime: string
  match_week?: string
  home_team: TeamBrief
  away_team: TeamBrief
  status: string              // "FINISHED" | "SCHEDULED" | "POSTPONED"
  outcome?: string
  home_goals?: number
  away_goals?: number
}

export interface MatchDetail extends MatchListItem {
  half_time_home_goals?: number
  half_time_away_goals?: number
  stadium?: { id: number; name: string; city?: string; capacity?: number }
  referee?: { id: number; name: string; country?: string }
  attendance?: number
  home_possession?: number
  away_possession?: number
  home_shots?: number
  away_shots?: number
  home_shots_on_target?: number
  away_shots_on_target?: number
  home_corners?: number
  away_corners?: number
}

export interface MatchesParams {
  season?: string
  status?: string
  team_id?: number
  page?: number
  page_size?: number
}

// ─── Team types ────────────────────────────────────────────────────────────────

export interface TeamSeasonStats {
  season_name: string
  matches_played: number
  wins: number
  draws: number
  losses: number
  goals_scored: number
  goals_conceded: number
  points: number
  ppg: number
  clean_sheets: number
  current_elo?: number
}

export interface TeamDetailResponse extends Team {
  current_season_stats?: TeamSeasonStats
  last_5_form?: TeamFormEntry[]
}

export interface TeamFormEntry {
  match_id: number
  match_date: string
  opponent_name: string
  location: string           // "Home" | "Away"
  goals_scored: number
  goals_conceded: number
  outcome: string            // "W" | "D" | "L"
  points: number
}

export interface TeamFormResponse {
  team: TeamBrief
  form: TeamFormEntry[]
  form_string: string        // e.g. "WWDLW"
  points_last_5: number
}

export interface TeamSplitStats {
  played: number
  wins: number
  draws: number
  losses: number
  goals_scored: number
  goals_conceded: number
  goal_difference: number
  points: number
  win_rate: number
  avg_goals_scored: number
  avg_goals_conceded: number
}

export interface TeamStatsResponse {
  team: TeamBrief
  season?: Season
  overall: TeamSplitStats
  home: TeamSplitStats
  away: TeamSplitStats
}

// ─── Head-to-Head types ────────────────────────────────────────────────────────

export interface H2HResponse {
  home_team: TeamBrief
  away_team: TeamBrief
  total_meetings: number
  home_wins: number
  draws: number
  away_wins: number
  avg_home_goals: number
  avg_away_goals: number
  over_2_5_rate: number
  btts_rate: number
  recent_matches: MatchListItem[]
}

// ─── Model types ───────────────────────────────────────────────────────────────

export interface ModelInfo {
  status: 'loaded' | 'not_loaded'
  version: string | null
  trained_at?: string | null
  training_seasons?: string[]
  n_features?: number
  feature_names?: string[]
  algorithm?: string
  cv_evaluation_model?: string | null
  walk_forward_folds?: number | null
  cv_metrics?: Record<string, number | null>
  baseline_cv_metrics?: Record<string, number | null>
}

export interface ModelPerformance {
  total_predictions: number
  evaluated: number
  correct?: number
  accuracy: number | null
  log_loss?: number | null
  brier_score?: number | null
  note?: string
}

// ─── Predictions list ──────────────────────────────────────────────────────────

export interface PredictionRecord {
  id: number
  match_id: number
  home_team_name: string
  away_team_name: string
  predicted_outcome: string
  home_win_prob: number
  draw_prob: number
  away_win_prob: number
  actual_outcome?: string
  was_correct?: boolean
  created_at: string
}
