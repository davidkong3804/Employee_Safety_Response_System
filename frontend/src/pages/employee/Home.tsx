import { useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import axios from 'axios'
import { AlertTriangle, CheckCircle, Clock, RefreshCw } from 'lucide-react'
import { listEvents } from '../../api/events'
import { getMyReport } from '../../api/reports'
import { getMyReminders, type MyReminder } from '../../api/reminders'
import { useAuth } from '../../contexts/AuthContext'
import ReminderModal from '../../components/ReminderModal'
import StatusBadge from '../../components/StatusBadge'
import type { Event, SafetyReport } from '../../types'

export default function Home() {
  const { t } = useTranslation()
  const { user } = useAuth()
  const location = useLocation()
  const [events, setEvents] = useState<Event[]>([])
  const [myReports, setMyReports] = useState<Record<string, SafetyReport | null>>({})
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<boolean>(false)
  const [retryNonce, setRetryNonce] = useState(0)
  const [modalReminders, setModalReminders] = useState<MyReminder[] | null>(null)

  // Re-fetch events (and per-event report status) whenever Home mounts, the
  // user navigates back here, or the user clicks "retry". `location.key`
  // changes on every navigation; `retryNonce` is a manual bump.
  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    setLoadError(false)
    ;(async () => {
      try {
        const evts = await listEvents({ signal: controller.signal })
        if (controller.signal.aborted) return
        setEvents(evts)
        const active = evts.filter(e => e.status === 'active')
        const pairs = await Promise.all(
          active.map(async (ev) => {
            try {
              const rpt = await getMyReport(ev.id, { signal: controller.signal })
              return [ev.id, rpt] as [string, SafetyReport | null]
            } catch {
              return [ev.id, null] as [string, null]
            }
          })
        )
        if (controller.signal.aborted) return
        setMyReports(Object.fromEntries(pairs))
      } catch (err) {
        if (axios.isCancel(err) || controller.signal.aborted) return
        // Don't drop into the "no events" empty state — surface the real
        // failure so the employee knows to retry instead of assuming all-clear.
        setEvents([])
        setMyReports({})
        setLoadError(true)
      } finally {
        if (!controller.signal.aborted) setLoading(false)
      }
    })()
    return () => controller.abort()
  }, [location.key, retryNonce])

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
            {activeEvents.map(event => {
              const myReport = myReports[event.id]
              const hasReported = myReport?.status != null

              return (
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
                    {hasReported && (
                      <div className="flex-shrink-0 ml-4 mt-1">
                        <StatusBadge status={myReport!.status} size="sm" />
                      </div>
                    )}
                  </div>

                  <div className="flex gap-3 mt-4">
                    <Link
                      to={`/events/${event.id}/report`}
                      className={`flex-1 text-center py-3 rounded-lg font-medium transition text-lg flex items-center justify-center gap-2 ${
                        hasReported
                          ? 'bg-gray-100 text-gray-700 border border-gray-300 hover:bg-gray-200'
                          : 'bg-blue-900 text-white hover:bg-blue-800'
                      }`}
                    >
                      {hasReported && <CheckCircle className="w-5 h-5 text-green-600" />}
                      {hasReported ? t('report.update') : t('report.title')}
                    </Link>
                  </div>
                </div>
              )
            })}
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

      {loadError && (
        <div className="text-center py-16">
          <AlertTriangle className="w-16 h-16 mx-auto mb-4 text-red-500" />
          <p className="text-lg text-red-700 font-medium mb-4">{t('event.loadError')}</p>
          <button
            type="button"
            onClick={() => setRetryNonce(n => n + 1)}
            className="inline-flex items-center gap-2 px-5 py-2.5 bg-blue-900 text-white rounded-lg font-medium hover:bg-blue-800 transition"
          >
            <RefreshCw className="w-4 h-4" />
            {t('common.retry')}
          </button>
        </div>
      )}

      {!loadError && events.length === 0 && (
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
