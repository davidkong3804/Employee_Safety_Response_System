import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import toast from 'react-hot-toast'
import { ArrowLeft, CheckCircle, AlertCircle } from 'lucide-react'
import { getEvent } from '../../api/events'
import { submitReport, getMyReport } from '../../api/reports'
import StatusBadge from '../../components/StatusBadge'
import type { Event, SafetyReport } from '../../types'

export default function ReportPage() {
  const { eventId } = useParams<{ eventId: string }>()
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [event, setEvent] = useState<Event | null>(null)
  const [myReport, setMyReport] = useState<SafetyReport | null>(null)
  const [message, setMessage] = useState('')
  const [loading, setLoading] = useState(false)
  const [submitted, setSubmitted] = useState(false)
  const [pageLoading, setPageLoading] = useState(true)

  useEffect(() => {
    if (!eventId) return
    Promise.all([
      getEvent(eventId),
      getMyReport(eventId),
    ]).then(([ev, rpt]) => {
      setEvent(ev)
      setMyReport(rpt)
    }).finally(() => setPageLoading(false))
  }, [eventId])

  const handleReport = async (status: 'safe' | 'need_help') => {
    if (!eventId || submitted) return
    // Optimistic lock — hides the buttons immediately so a tap and a
    // delayed second tap can't both fire before React renders loading=true.
    setSubmitted(true)
    setLoading(true)
    try {
      const report = await submitReport(eventId, { status, message: message || undefined })
      setMyReport(report)
      toast.success(t('report.submitted'))
      navigate('/', { state: { refresh: true } })
    } catch {
      setSubmitted(false)  // let the user retry on error
      toast.error(t('report.failed'))
    } finally {
      setLoading(false)
    }
  }

  if (pageLoading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-900" />
      </div>
    )
  }

  const alreadyReported = submitted || (myReport?.status !== null && myReport?.status !== undefined)

  return (
    <div className="max-w-lg mx-auto p-6">
      <button onClick={() => navigate('/')} className="flex items-center gap-1 text-gray-500 hover:text-gray-800 mb-6">
        <ArrowLeft className="w-5 h-5" />
        {t('nav.home')}
      </button>

      <div className="text-center mb-8">
        <h1 className="text-2xl font-bold text-gray-900">{t('report.title')}</h1>
        <p className="text-gray-500 mt-2">{event?.title}</p>
      </div>

      {alreadyReported ? (
        <div className="text-center py-12">
          <CheckCircle className="w-20 h-20 text-green-500 mx-auto mb-4" />
          <p className="text-lg font-medium text-gray-700 mb-2">{t('report.alreadyReported')}</p>
          {myReport?.status && (
            <>
              <p className="text-gray-500 mb-4">{t('report.status')}:</p>
              <StatusBadge status={myReport.status} size="md" />
              {myReport.message && (
                <p className="mt-4 text-gray-600 bg-gray-50 rounded-lg p-3">{myReport.message}</p>
              )}
            </>
          )}
        </div>
      ) : (
        <div className="flex flex-col items-center gap-8">
          <button
            onClick={() => handleReport('safe')}
            disabled={loading}
            className="w-56 h-56 rounded-full bg-green-500 text-white text-2xl font-bold shadow-xl hover:bg-green-600 active:scale-95 transition-all disabled:opacity-50 flex flex-col items-center justify-center gap-2"
          >
            <CheckCircle className="w-12 h-12" />
            {t('report.imSafe')}
          </button>

          <div className="w-full">
            <textarea
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder={t('report.message')}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 resize-none"
              rows={2}
            />
          </div>

          <button
            onClick={() => handleReport('need_help')}
            disabled={loading}
            className="w-40 h-40 rounded-full bg-red-500 text-white text-lg font-bold shadow-xl hover:bg-red-600 active:scale-95 transition-all disabled:opacity-50 flex flex-col items-center justify-center gap-2"
          >
            <AlertCircle className="w-10 h-10" />
            {t('report.needHelp')}
          </button>
        </div>
      )}
    </div>
  )
}
