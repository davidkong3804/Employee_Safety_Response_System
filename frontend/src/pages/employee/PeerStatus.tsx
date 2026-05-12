import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { ArrowLeft, Phone } from 'lucide-react'
import { getTeamStatus } from '../../api/reports'
import StatusBadge from '../../components/StatusBadge'
import type { SafetyReport } from '../../types'

export default function PeerStatus() {
  const { eventId } = useParams<{ eventId: string }>()
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [reports, setReports] = useState<SafetyReport[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!eventId) return
    getTeamStatus(eventId).then(setReports).finally(() => setLoading(false))
  }, [eventId])

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-900" />
      </div>
    )
  }

  const sorted = [...reports].sort((a, b) => {
    const order = { need_help: 0, null: 1, safe: 2 }
    const aKey = (a.status ?? 'null') as keyof typeof order
    const bKey = (b.status ?? 'null') as keyof typeof order
    return (order[aKey] ?? 1) - (order[bKey] ?? 1)
  })

  return (
    <div className="max-w-2xl mx-auto p-6">
      <button onClick={() => navigate('/home')} className="flex items-center gap-1 text-gray-500 hover:text-gray-800 mb-6">
        <ArrowLeft className="w-5 h-5" />
        {t('nav.home')}
      </button>

      <h1 className="text-2xl font-bold text-gray-900 mb-6">{t('peers.title')}</h1>

      <div className="space-y-3">
        {sorted.map(report => (
          <div key={report.id} className="bg-white rounded-lg p-4 shadow-sm border border-gray-100 flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className={`w-3 h-3 rounded-full ${
                report.status === 'safe' ? 'bg-green-500' :
                report.status === 'need_help' ? 'bg-red-500 animate-pulse' :
                'bg-gray-300'
              }`} />
              <div>
                <p className="font-medium">{report.user_name}</p>
                <p className="text-sm text-gray-500">{report.employee_id} | {report.department}</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <StatusBadge status={report.status} />
              {report.phone && (
                <a href={`tel:${report.phone}`} className="text-blue-600 hover:text-blue-800" title={t('peers.call')}>
                  <Phone className="w-4 h-4" />
                </a>
              )}
            </div>
          </div>
        ))}

        {reports.length === 0 && (
          <p className="text-center text-gray-400 py-12">No team data</p>
        )}
      </div>
    </div>
  )
}
