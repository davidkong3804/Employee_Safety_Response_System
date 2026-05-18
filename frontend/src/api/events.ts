import client from './client'
import type { Event } from '../types'

export async function listEvents() {
  const { data } = await client.get('/api/events')
  return data as Event[]
}

export async function getEvent(id: string) {
  const { data } = await client.get(`/api/events/${id}`)
  return data as Event
}

export async function createEvent(payload: {
  title: string
  description?: string
  event_type: string
  severity: string
  facility?: string[]
}) {
  const { data } = await client.post('/api/events', payload)
  return data as Event
}

export async function updateEvent(id: string, payload: Record<string, unknown>) {
  const { data } = await client.patch(`/api/events/${id}`, payload)
  return data as Event
}

export async function deleteEvent(id: string) {
  await client.delete(`/api/events/${id}`)
}
