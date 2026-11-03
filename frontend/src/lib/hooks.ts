import { useQuery, useMutation } from '@tanstack/react-query'
import * as api from './api'
import type { MatchesParams, PredictRequest } from './types'

export const useMatches = (params?: MatchesParams) =>
  useQuery({
    queryKey: ['matches', params],
    queryFn: () => api.getMatches(params).then((r) => r.data),
  })

export const useMatch = (id: number) =>
  useQuery({
    queryKey: ['match', id],
    queryFn: () => api.getMatch(id).then((r) => r.data),
    enabled: !!id,
  })

export const useSeasons = () =>
  useQuery({
    queryKey: ['seasons'],
    queryFn: () => api.getSeasons().then((r) => r.data),
  })

export const useTeams = () =>
  useQuery({
    queryKey: ['teams'],
    queryFn: () => api.getTeams({ page_size: 100 }).then((r) => r.data),
  })

export const useTeam = (id: number) =>
  useQuery({
    queryKey: ['team', id],
    queryFn: () => api.getTeam(id).then((r) => r.data),
    enabled: !!id,
  })

export const useTeamForm = (id: number) =>
  useQuery({
    queryKey: ['teamForm', id],
    queryFn: () => api.getTeamForm(id).then((r) => r.data),
    enabled: !!id,
  })

export const useTeamStats = (id: number) =>
  useQuery({
    queryKey: ['teamStats', id],
    queryFn: () => api.getTeamStats(id).then((r) => r.data),
    enabled: !!id,
  })

export const useHeadToHead = (homeId?: number, awayId?: number) =>
  useQuery({
    queryKey: ['h2h', homeId, awayId],
    queryFn: () => api.getHeadToHead(homeId!, awayId!).then((r) => r.data),
    enabled: !!homeId && !!awayId,
  })

export const usePredictions = (params?: { page?: number; page_size?: number }) =>
  useQuery({
    queryKey: ['predictions', params],
    queryFn: () => api.getPredictions(params).then((r) => r.data),
  })

export const useModelInfo = () =>
  useQuery({
    queryKey: ['modelInfo'],
    queryFn: () => api.getModelInfo().then((r) => r.data),
  })

export const useModelPerformance = () =>
  useQuery({
    queryKey: ['modelPerformance'],
    queryFn: () => api.getModelPerformance().then((r) => r.data),
  })

export const usePredict = () =>
  useMutation({
    mutationFn: (data: PredictRequest) =>
      api.predictMatch(data).then((r) => r.data),
  })
