import client from './client'
import type { User } from '../types'

export async function login(employee_id: string, password: string) {
  const { data } = await client.post('/api/auth/login', { employee_id, password })
  return data as { access_token: string; token_type: string }
}

export async function getMe() {
  const { data } = await client.get('/api/auth/me')
  return data as User
}
