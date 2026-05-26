import client from './client'

export interface MyReminder {
  event_id: string
  event_title: string
  severity: string
  reminder_count: number
  last_reminded: string | null
}

export async function getMyReminders() {
  const { data } = await client.get('/api/me/reminders')
  return data as MyReminder[]
}
