import axios from 'axios'
import type { Competition } from './competition'
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
export const predictMatch = (data: PredictRequest, league?: string) =>
  api.post<PredictResponse>('/api/v1/predictions', data, { params: { league } })

/** GET /api/v1/predictions - List stored predictions (paginated) */
export const getPredictions = (params?: { page?: number; page_size?: number }, league?: string) =>
  api.get<PagedResponse<PredictionRecord>>('/api/v1/predictions', { params: { ...params, league } })

// ── Matches ──────────────────────────────────────────────────────────────────

/** GET /api/v1/matches - List matches with optional filters */
export const getMatches = (params?: MatchesParams, league?: string) =>
  api.get<PagedResponse<MatchListItem>>('/api/v1/matches', { params: { ...params, league } })

export const getSeasons = (league?: string) =>
  api.get<string[]>('/api/v1/matches/seasons', { params: { league } })

/** GET /api/v1/matches/:id - Match detail */
export const getMatch = (id: number, league?: string) =>
  api.get<MatchDetail>(`/api/v1/matches/${id}`, { params: { league } })

// ── Teams ────────────────────────────────────────────────────────────────────

/** GET /api/v1/teams - List teams (paginated) */
export const getTeams = (params?: { search?: string; page?: number; page_size?: number }, league?: string) =>
  api.get<PagedResponse<Team>>('/api/v1/teams', { params: { ...params, league } })

/** GET /api/v1/teams/:id - Team detail */
export const getTeam = (id: number, league?: string) =>
  api.get<TeamDetailResponse>(`/api/v1/teams/${id}`, { params: { league } })

/** GET /api/v1/teams/:id/form - Team recent form */
export const getTeamForm = (id: number, league?: string) =>
  api.get<TeamFormResponse>(`/api/v1/teams/${id}/form`, { params: { league } })

/** GET /api/v1/teams/:id/stats - Team season stats with home/away split */
export const getTeamStats = (id: number, league?: string) =>
  api.get<TeamStatsResponse>(`/api/v1/teams/${id}/stats`, { params: { league } })

/** GET /api/v1/teams/head-to-head - H2H between two teams */
export const getHeadToHead = (homeId: number, awayId: number, league?: string) =>
  api.get<H2HResponse>('/api/v1/teams/head-to-head', {
    params: { home_team_id: homeId, away_team_id: awayId, league },
  })

// ── Model ────────────────────────────────────────────────────────────────────

export const getModelInfo = (league?: string) =>
  api.get<ModelInfo>('/api/v1/model/info', { params: { league } })

export const getModelPerformance = (league?: string) =>
  api.get<ModelPerformance>('/api/v1/model/performance', { params: { league } })

export const getCompetitions = () => api.get<Competition[]>('/api/v1/leagues')

export default api
