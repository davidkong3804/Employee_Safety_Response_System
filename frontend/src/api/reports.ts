import client from './client'
import type { SafetyReport, EventStats, DepartmentStats, PaginatedReports } from '../types'

export interface TeamStatusParams {
  limit?: number
  offset?: number
  status?: 'safe' | 'need_help' | 'unreported'
  search?: string
  department?: string
}

export interface AllStatusParams extends TeamStatusParams {
  facility?: string
}

export async function submitReport(eventId: string, payload: { status: string; message?: string }) {
  const { data } = await client.post(`/api/events/${eventId}/report`, payload)
  return data as SafetyReport
}

export async function getMyReport(eventId: string, config?: { signal?: AbortSignal }) {
  const { data } = await client.get(`/api/events/${eventId}/my-report`, config)
  return data as SafetyReport | null
}

export async function getEventStats(eventId: string) {
  const { data } = await client.get(`/api/events/${eventId}/stats`)
  return data as EventStats
}

export async function getStatsByDepartment(eventId: string) {
  const { data } = await client.get(`/api/events/${eventId}/stats/by-department`)
  return data as DepartmentStats[]
}

export async function getTeamStatus(eventId: string, params: TeamStatusParams = {}) {
  const { data } = await client.get(`/api/events/${eventId}/team-status`, { params })
  return data as PaginatedReports
}

export async function getAllStatus(eventId: string, params: AllStatusParams = {}) {
  const { data } = await client.get(`/api/events/${eventId}/all-status`, { params })
  return data as PaginatedReports
}

export async function triggerReminders(eventId: string) {
  const { data } = await client.post(`/api/events/${eventId}/remind`)
  return data as { reminded_count: number; message: string }
}
