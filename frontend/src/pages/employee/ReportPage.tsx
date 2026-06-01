import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import toast from 'react-hot-toast'
import { isAxiosError } from 'axios'
import { ArrowLeft, CheckCircle, AlertCircle } from 'lucide-react'
import { getEvent } from '../../api/events'
import { submitReport, getMyReport } from '../../api/reports'
import StatusBadge from '../../components/StatusBadge'
import type { Event, SafetyReport } from '../../types'

const SUBMIT_ERROR_TOAST_ID = 'report-submit-error'

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
  const [error, setError] = useState(false)
  // FEATURE-2: guard the "Need Help" action behind an explicit confirmation so
  // an accidental tap doesn't dispatch a medical-assistance request.
  const [confirmHelp, setConfirmHelp] = useState(false)

  useEffect(() => {
    if (!eventId) return
    setError(false)
    setPageLoading(true)
    Promise.all([
      getEvent(eventId),
      getMyReport(eventId),
    ]).then(([ev, rpt]) => {
      setEvent(ev)
      setMyReport(rpt)
    }).catch(err => {
      console.error('Failed to load event or report:', err)
      setError(true)
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
      toast.dismiss(SUBMIT_ERROR_TOAST_ID)
      toast.success(t('report.submitted'))
      navigate('/', { state: { refresh: true } })
    } catch (err) {
      setSubmitted(false)  // let the user retry on error
      let msgKey = 'report.failed'
      if (isAxiosError(err)) {
        if (err.response?.status === 429) {
          msgKey = 'report.failedRateLimit'
        } else if (!err.response || err.code === 'ECONNABORTED') {
          msgKey = 'report.failedNetwork'
        } else if (err.response.status === 500) {
          msgKey = 'report.failedAmbiguous'
        } else if (err.response.status >= 500) {
          msgKey = 'report.failedServer'
        }
      }
      // Single toast id — repeat failures replace the existing toast
      // instead of stacking, so the screen doesn't fill up under spike load.
      toast.error(t(msgKey), { id: SUBMIT_ERROR_TOAST_ID })
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

  if (error || !event) {
    return (
      <div className="max-w-md mx-auto p-6 flex flex-col items-center justify-center min-h-[50vh] text-center animate-fade-in">
        <div className="bg-white rounded-2xl p-8 shadow-xl border border-gray-100">
          <div className="w-16 h-16 bg-red-50 text-red-500 rounded-2xl flex items-center justify-center mx-auto mb-6">
            <AlertCircle className="w-8 h-8" />
          </div>
          <h1 className="text-xl font-bold text-gray-950 mb-2">{t('event.loadError')}</h1>
          <p className="text-sm text-gray-500 mb-6 leading-relaxed">
            The requested safety event could not be found or failed to load.
          </p>
          <button
            onClick={() => navigate('/')}
            className="w-full py-3 bg-blue-900 hover:bg-blue-800 text-white font-semibold rounded-xl shadow transition"
          >
            {t('nav.home')}
          </button>
        </div>
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

      {alreadyReported && myReport?.status && (
        <div className="text-center mb-8 pb-6 border-b border-gray-200">
          {myReport.status === 'need_help' ? (
            <AlertCircle className="w-16 h-16 text-red-500 mx-auto mb-3" />
          ) : (
            <CheckCircle className="w-16 h-16 text-green-500 mx-auto mb-3" />
          )}
          <p className="text-lg font-medium text-gray-700 mb-2">{t('report.alreadyReported')}</p>
          <p className="text-gray-500 mb-3">{t('report.status')}:</p>
          <StatusBadge status={myReport.status} size="md" />
          {myReport.message && (
            <p className="mt-4 text-gray-600 bg-gray-50 rounded-lg p-3">{myReport.message}</p>
          )}
          {/* FEATURE-1: surface the employee id + report timestamp recorded with
              this report so the employee can see their report content carries
              their 員工編號 and 回報時間. */}
          <p className="mt-3 text-xs text-gray-400">
            {myReport.employee_id}
            {myReport.reported_at ? ` · ${new Date(myReport.reported_at).toLocaleString()}` : ''}
          </p>
          <p className="mt-6 text-sm text-gray-500">{t('report.updateHint')}</p>
        </div>
      )}

      <div className="grid grid-cols-2 gap-4">
        <button
          onClick={() => handleReport('safe')}
          disabled={loading || submitted}
          className="w-full aspect-square rounded-2xl bg-green-500 text-white text-2xl font-bold shadow-xl hover:bg-green-600 active:scale-95 transition-all disabled:opacity-50 flex flex-col items-center justify-center gap-3"
        >
          <CheckCircle className="w-16 h-16" />
          {t('report.imSafe')}
        </button>
        <div className="flex flex-col gap-3">
          <button
            onClick={() => setConfirmHelp(true)}
            disabled={loading || submitted}
            className="w-full aspect-square rounded-2xl bg-red-500 text-white text-2xl font-bold shadow-xl hover:bg-red-600 active:scale-95 transition-all disabled:opacity-50 flex flex-col items-center justify-center gap-3"
          >
            <AlertCircle className="w-16 h-16" />
            {t('report.needHelp')}
          </button>
          <textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder={t('report.message')}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 resize-none"
            rows={2}
          />
        </div>
      </div>

      {confirmHelp && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center z-50 p-4 animate-fade-in">
          <div className="bg-white rounded-2xl p-6 w-full max-w-sm shadow-2xl border border-gray-100">
            <div className="w-14 h-14 bg-red-50 text-red-500 rounded-2xl flex items-center justify-center mx-auto mb-4">
              <AlertCircle className="w-8 h-8" />
            </div>
            <h3 className="text-lg font-bold text-gray-950 text-center mb-2">{t('report.confirmHelpTitle')}</h3>
            <p className="text-sm text-gray-500 text-center mb-6 leading-relaxed">{t('report.confirmHelpBody')}</p>
            <div className="grid grid-cols-2 gap-3">
              <button
                onClick={() => setConfirmHelp(false)}
                className="py-3 rounded-xl border border-gray-300 text-gray-700 font-semibold hover:bg-gray-50 transition"
              >
                {t('common.cancel')}
              </button>
              <button
                onClick={() => {
                  setConfirmHelp(false)
                  handleReport('need_help')
                }}
                className="py-3 rounded-xl bg-red-500 text-white font-semibold hover:bg-red-600 transition"
              >
                {t('report.confirmHelpConfirm')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
