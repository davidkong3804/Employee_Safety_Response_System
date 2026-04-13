import client from './client'
import type { SafetyReport, EventStats, DepartmentStats } from '../types'

export async function submitReport(eventId: string, payload: { status: string; message?: string }) {
  const { data } = await client.post(`/api/events/${eventId}/report`, payload)
  return data as SafetyReport
}

export async function getMyReport(eventId: string) {
  const { data } = await client.get(`/api/events/${eventId}/my-report`)
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

export async function getTeamStatus(eventId: string) {
  const { data } = await client.get(`/api/events/${eventId}/team-status`)
  return data as SafetyReport[]
}

export async function getAllStatus(eventId: string, facility?: string, department?: string) {
  const params = new URLSearchParams()
  if (facility) params.set('facility', facility)
  if (department) params.set('department', department)
  const { data } = await client.get(`/api/events/${eventId}/all-status?${params}`)
  return data as SafetyReport[]
}

export async function triggerReminders(eventId: string) {
  const { data } = await client.post(`/api/events/${eventId}/remind`)
  return data as { reminded_count: number; message: string }
}
