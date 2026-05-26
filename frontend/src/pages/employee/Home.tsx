import { useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { AlertTriangle, CheckCircle, Clock } from 'lucide-react'
import { listEvents } from '../../api/events'
import { getMyReminders, type MyReminder } from '../../api/reminders'
import { useAuth } from '../../contexts/AuthContext'
import ReminderModal from '../../components/ReminderModal'
import type { Event } from '../../types'

export default function Home() {
  const { t } = useTranslation()
  const { user } = useAuth()
  const location = useLocation()
  const [events, setEvents] = useState<Event[]>([])
  const [loading, setLoading] = useState(true)
  const [modalReminders, setModalReminders] = useState<MyReminder[] | null>(null)

  // Re-fetch events whenever Home mounts OR ReportPage navigates back with
  // `{ state: { refresh: true } }` after a successful report. `location.key`
  // changes on every navigation so this also covers re-entering from any
  // other page.
  useEffect(() => {
    setLoading(true)
    listEvents().then(setEvents).finally(() => setLoading(false))
  }, [location.key])

  // Show the reminder modal ONCE per login, on the first visit to Home.
  // The flag is set by AuthContext.login() and cleared here after one read.
  useEffect(() => {
    if (!user || user.role !== 'employee') return
    if (sessionStorage.getItem('reminder-modal-pending') !== '1') return
    sessionStorage.removeItem('reminder-modal-pending')
    getMyReminders()
      .then((data) => {
        if (data.length > 0) setModalReminders(data)
      })
      .catch(() => {
        // Silent — modal just won't show. Banner will still cover it on poll.
      })
  }, [user])

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
          <p className="text-lg">{t('event.noEvents')}</p>
        </div>
      )}

      {modalReminders && (
        <ReminderModal
          reminders={modalReminders}
          onClose={() => setModalReminders(null)}
        />
      )}
    </div>
  )
}
