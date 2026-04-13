import client from './client'
import type { UserFull } from '../types'

export async function listUsers(params?: { role?: string; facility?: string; department?: string }) {
  const { data } = await client.get('/api/users', { params })
  return data as UserFull[]
}

export async function createUser(payload: Record<string, unknown>) {
  const { data } = await client.post('/api/users', payload)
  return data as UserFull
}

export async function updateUser(id: string, payload: Record<string, unknown>) {
  const { data } = await client.patch(`/api/users/${id}`, payload)
  return data as UserFull
}

export async function deleteUser(id: string) {
  await client.delete(`/api/users/${id}`)
}
