import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { AlertTriangle, CheckCircle, Clock, Users } from 'lucide-react'
import { listEvents } from '../../api/events'
import { useAuth } from '../../contexts/AuthContext'
import type { Event } from '../../types'

export default function Home() {
  const { t } = useTranslation()
  const { user } = useAuth()
  const [events, setEvents] = useState<Event[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    listEvents().then(setEvents).finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-900" />
      </div>
    )
  }

  const activeEvents = events.filter(e => e.status === 'active')
  const closedEvents = events.filter(e => e.status === 'closed')

  const severityColors: Record<string, string> = {
    low: 'border-yellow-400 bg-yellow-50',
    medium: 'border-orange-400 bg-orange-50',
    high: 'border-red-400 bg-red-50',
    critical: 'border-red-600 bg-red-100',
  }

  const severityIcons: Record<string, string> = {
    low: 'text-yellow-500',
    medium: 'text-orange-500',
    high: 'text-red-500',
    critical: 'text-red-700',
  }

  return (
    <div className="max-w-4xl mx-auto p-6">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">{t('nav.home')}</h1>
        <p className="text-gray-500 mt-1">
          {user?.name} - {user?.department} / {user?.facility}
        </p>
      </div>

      {activeEvents.length > 0 && (
        <div className="mb-8">
          <h2 className="text-lg font-semibold text-red-700 flex items-center gap-2 mb-4">
            <AlertTriangle className="w-5 h-5" />
            {t('event.active')}
          </h2>
          <div className="space-y-4">
            {activeEvents.map(event => (
              <div key={event.id} className={`border-l-4 rounded-lg p-6 shadow-sm ${severityColors[event.severity]}`}>
                <div className="flex items-start justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <AlertTriangle className={`w-5 h-5 ${severityIcons[event.severity]}`} />
                      <h3 className="text-lg font-bold">{event.title}</h3>
                    </div>
                    <p className="text-gray-600 mt-1">{event.description}</p>
                    <div className="flex items-center gap-4 mt-2 text-sm text-gray-500">
                      <span className="flex items-center gap-1">
                        <Clock className="w-4 h-4" />
                        {new Date(event.created_at).toLocaleString()}
                      </span>
                      <span className="px-2 py-0.5 rounded bg-red-200 text-red-800 text-xs font-medium">
                        {t(`event.severities.${event.severity}`)}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="flex gap-3 mt-4">
                  <Link
                    to={`/events/${event.id}/report`}
                    className="flex-1 text-center py-3 bg-blue-900 text-white rounded-lg font-medium hover:bg-blue-800 transition text-lg"
                  >
                    {t('report.title')}
                  </Link>
                  <Link
                    to={`/events/${event.id}/peers`}
                    className="flex items-center justify-center gap-2 px-6 py-3 bg-white border border-gray-300 rounded-lg font-medium hover:bg-gray-50 transition"
                  >
                    <Users className="w-5 h-5" />
                    {t('peers.title')}
                  </Link>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {closedEvents.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold text-gray-500 flex items-center gap-2 mb-4">
            <CheckCircle className="w-5 h-5" />
            {t('event.closed')}
          </h2>
          <div className="space-y-3">
            {closedEvents.map(event => (
              <div key={event.id} className="border border-gray-200 rounded-lg p-4 bg-white opacity-70">
                <h3 className="font-medium text-gray-700">{event.title}</h3>
                <p className="text-sm text-gray-500 mt-1">
                  {t(`event.types.${event.event_type}`)} | {new Date(event.created_at).toLocaleDateString()}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {events.length === 0 && (
        <div className="text-center py-16 text-gray-400">
          <CheckCircle className="w-16 h-16 mx-auto mb-4" />
          <p className="text-lg">No active events</p>
        </div>
      )}
    </div>
  )
}
