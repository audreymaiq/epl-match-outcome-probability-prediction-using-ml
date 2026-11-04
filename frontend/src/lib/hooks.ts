import { useQuery, useMutation } from '@tanstack/react-query'
import * as api from './api'
import type { MatchesParams, PredictRequest } from './types'
import { useCompetition } from './competition'

function useCompetitionQuery<T>(key: readonly unknown[], load: (league: string) => Promise<T>, enabled = true) {
  const { league, ready } = useCompetition()
  return useQuery({ queryKey: [league, ...key], queryFn: () => load(league), enabled: ready && enabled })
}

export const useMatches = (params?: MatchesParams) =>
  useCompetitionQuery(['matches', params], (league) => api.getMatches(params, league).then((r) => r.data))

export const useMatch = (id: number) =>
  useCompetitionQuery(['match', id], (league) => api.getMatch(id, league).then((r) => r.data), !!id)

export const useSeasons = () =>
  useCompetitionQuery(['seasons'], (league) => api.getSeasons(league).then((r) => r.data))

export const useTeams = () =>
  useCompetitionQuery(['teams'], (league) => api.getTeams({ page_size: 100 }, league).then((r) => r.data))

export const useTeam = (id: number) =>
  useCompetitionQuery(['team', id], (league) => api.getTeam(id, league).then((r) => r.data), !!id)

export const useTeamForm = (id: number) =>
  useCompetitionQuery(['teamForm', id], (league) => api.getTeamForm(id, league).then((r) => r.data), !!id)

export const useTeamStats = (id: number) =>
  useCompetitionQuery(['teamStats', id], (league) => api.getTeamStats(id, league).then((r) => r.data), !!id)

export const useHeadToHead = (homeId?: number, awayId?: number) =>
  useCompetitionQuery(['h2h', homeId, awayId], (league) => api.getHeadToHead(homeId!, awayId!, league).then((r) => r.data), !!homeId && !!awayId)

export const usePredictions = (params?: { page?: number; page_size?: number }) =>
  useCompetitionQuery(['predictions', params], (league) => api.getPredictions(params, league).then((r) => r.data))

export const useModelInfo = () =>
  useCompetitionQuery(['modelInfo'], (league) => api.getModelInfo(league).then((r) => r.data))

export const useModelPerformance = () =>
  useCompetitionQuery(['modelPerformance'], (league) => api.getModelPerformance(league).then((r) => r.data))

export function usePredict() {
  const { league } = useCompetition()
  return useMutation({ mutationFn: (data: PredictRequest) => api.predictMatch(data, league).then((r) => r.data) })
}
