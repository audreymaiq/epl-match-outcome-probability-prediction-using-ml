import axios from 'axios'
import type {
  PredictRequest,
  PredictResponse,
  MatchesParams,
  MatchListItem,
  MatchDetail,
  Team,
  TeamDetailResponse,
  TeamFormResponse,
  TeamStatsResponse,
  H2HResponse,
  ModelInfo,
  ModelPerformance,
  PredictionRecord,
  PagedResponse,
} from './types'

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || '',
  timeout: 10000,
})

// ── Predictions ──────────────────────────────────────────────────────────────

/** POST /api/v1/predictions - Create a new prediction */
export const predictMatch = (data: PredictRequest) =>
  api.post<PredictResponse>('/api/v1/predictions', data)

/** GET /api/v1/predictions - List stored predictions (paginated) */
export const getPredictions = (params?: { page?: number; page_size?: number }) =>
  api.get<PagedResponse<PredictionRecord>>('/api/v1/predictions', { params })

// ── Matches ──────────────────────────────────────────────────────────────────

/** GET /api/v1/matches - List matches with optional filters */
export const getMatches = (params?: MatchesParams) =>
  api.get<PagedResponse<MatchListItem>>('/api/v1/matches', { params })

/** GET /api/v1/matches/:id - Match detail */
export const getMatch = (id: number) =>
  api.get<MatchDetail>(`/api/v1/matches/${id}`)

// ── Teams ────────────────────────────────────────────────────────────────────

/** GET /api/v1/teams - List teams (paginated) */
export const getTeams = (params?: { search?: string; page?: number; page_size?: number }) =>
  api.get<PagedResponse<Team>>('/api/v1/teams', { params })

/** GET /api/v1/teams/:id - Team detail */
export const getTeam = (id: number) =>
  api.get<TeamDetailResponse>(`/api/v1/teams/${id}`)

/** GET /api/v1/teams/:id/form - Team recent form */
export const getTeamForm = (id: number) =>
  api.get<TeamFormResponse>(`/api/v1/teams/${id}/form`)

/** GET /api/v1/teams/:id/stats - Team season stats with home/away split */
export const getTeamStats = (id: number) =>
  api.get<TeamStatsResponse>(`/api/v1/teams/${id}/stats`)

/** GET /api/v1/teams/head-to-head - H2H between two teams */
export const getHeadToHead = (homeId: number, awayId: number) =>
  api.get<H2HResponse>('/api/v1/teams/head-to-head', {
    params: { home_team_id: homeId, away_team_id: awayId },
  })

// ── Model ────────────────────────────────────────────────────────────────────

export const getModelInfo = () =>
  api.get<ModelInfo>('/api/v1/model/info')

export const getModelPerformance = () =>
  api.get<ModelPerformance>('/api/v1/model/performance')

export default api
