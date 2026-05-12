import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import toast from 'react-hot-toast'
import { Plus, X, AlertTriangle } from 'lucide-react'
import { listEvents, createEvent, updateEvent, deleteEvent } from '../../api/events'
import FacilitySelector from '../../components/FacilitySelector'
import type { Event } from '../../types'

export default function EventManagement() {
  const { t } = useTranslation()
  const [events, setEvents] = useState<Event[]>([])
  const [showCreate, setShowCreate] = useState(false)
  const [loading, setLoading] = useState(true)
  const [form, setForm] = useState({ title: '', description: '', event_type: 'earthquake', severity: 'high', facilities: [] as string[] })

  const load = () => {
    listEvents().then(setEvents).finally(() => setLoading(false))
  }

  useEffect(load, [])

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      const { facilities, ...rest } = form
      await createEvent({ ...rest, facility: facilities.length > 0 ? facilities : undefined })
      toast.success(t('event.createSuccess'))
      setShowCreate(false)
      setForm({ title: '', description: '', event_type: 'earthquake', severity: 'high', facilities: [] })
      load()
    } catch {
      toast.error(t('event.createFailed'))
    }
  }

  const handleClose = async (id: string) => {
    await updateEvent(id, { status: 'closed' })
    toast.success(t('event.closeSuccess'))
    load()
  }

  const handleDelete = async (id: string) => {
    await deleteEvent(id)
    toast.success(t('event.deleteSuccess'))
    load()
  }

  const severityBadge = (s: string) => {
    const colors: Record<string, string> = {
      low: 'bg-yellow-100 text-yellow-800',
      medium: 'bg-orange-100 text-orange-800',
      high: 'bg-red-100 text-red-800',
      critical: 'bg-red-200 text-red-900',
    }
    return <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${colors[s] || ''}`}>{t(`event.severities.${s}`)}</span>
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-900" />
      </div>
    )
  }

  return (
    <div className="max-w-5xl mx-auto p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">{t('nav.events')}</h1>
        <button onClick={() => setShowCreate(true)} className="flex items-center gap-2 px-4 py-2 bg-blue-900 text-white rounded-lg hover:bg-blue-800 transition">
          <Plus className="w-4 h-4" />
          {t('event.create')}
        </button>
      </div>

      {/* Create Modal */}
      {showCreate && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-6 w-full max-w-lg">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-bold">{t('event.create')}</h2>
              <button onClick={() => setShowCreate(false)}><X className="w-5 h-5" /></button>
            </div>
            <form onSubmit={handleCreate} className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">{t('event.title')}</label>
                <input value={form.title} onChange={e => setForm({...form, title: e.target.value})} className="w-full px-3 py-2 border rounded-lg" required />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">{t('event.description')}</label>
                <textarea value={form.description} onChange={e => setForm({...form, description: e.target.value})} className="w-full px-3 py-2 border rounded-lg" rows={3} />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-1">{t('event.type')}</label>
                  <select value={form.event_type} onChange={e => setForm({...form, event_type: e.target.value})} className="w-full px-3 py-2 border rounded-lg">
                    {['earthquake', 'fire', 'flood', 'security', 'other'].map(type => (
                      <option key={type} value={type}>{t(`event.types.${type}`)}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">{t('event.severity')}</label>
                  <select value={form.severity} onChange={e => setForm({...form, severity: e.target.value})} className="w-full px-3 py-2 border rounded-lg">
                    {['low', 'medium', 'high', 'critical'].map(s => (
                      <option key={s} value={s}>{t(`event.severities.${s}`)}</option>
                    ))}
                  </select>
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">{t('facility.selectFacilities')}</label>
                <FacilitySelector
                  value={form.facilities}
                  onChange={facilities => setForm({ ...form, facilities })}
                />
              </div>
              <button type="submit" className="w-full py-2 bg-blue-900 text-white rounded-lg hover:bg-blue-800 transition">
                {t('event.create')}
              </button>
            </form>
          </div>
        </div>
      )}

      {/* Events Table */}
      <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50 text-left text-sm text-gray-500">
            <tr>
              <th className="px-4 py-3">{t('event.title')}</th>
              <th className="px-4 py-3">{t('event.type')}</th>
              <th className="px-4 py-3">{t('event.severity')}</th>
              <th className="px-4 py-3">{t('event.facility')}</th>
              <th className="px-4 py-3">{t('report.status')}</th>
              <th className="px-4 py-3">{t('event.createdAt')}</th>
              <th className="px-4 py-3">{t('common.actions')}</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {events.map(ev => (
              <tr key={ev.id} className={ev.status === 'active' ? 'bg-red-50/50' : ''}>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    {ev.status === 'active' && <AlertTriangle className="w-4 h-4 text-red-500" />}
                    <span className="font-medium">{ev.title}</span>
                  </div>
                </td>
                <td className="px-4 py-3 text-sm">{t(`event.types.${ev.event_type}`)}</td>
                <td className="px-4 py-3">{severityBadge(ev.severity)}</td>
                <td className="px-4 py-3 text-sm">{ev.facility && ev.facility.length > 0 ? ev.facility.join(', ') : t('event.allFacilities')}</td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                    ev.status === 'active' ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-600'
                  }`}>{t(`event.${ev.status}`)}</span>
                </td>
                <td className="px-4 py-3 text-sm text-gray-500">{new Date(ev.created_at).toLocaleString()}</td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    {ev.status === 'active' && (
                      <button onClick={() => handleClose(ev.id)} className="text-xs px-2 py-1 bg-yellow-100 text-yellow-800 rounded hover:bg-yellow-200">
                        {t('event.close')}
                      </button>
                    )}
                    <button onClick={() => handleDelete(ev.id)} className="text-xs px-2 py-1 bg-red-100 text-red-800 rounded hover:bg-red-200">
                      {t('event.delete')}
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
