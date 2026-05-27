import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend } from 'recharts'
import { Activity, Users, AlertTriangle, TrendingUp } from 'lucide-react'
import { listEvents } from '../../api/events'
import { getEventStats } from '../../api/reports'
import { listUsers } from '../../api/users'
import type { Event, EventStats } from '../../types'

const COLORS = ['#22c55e', '#ef4444', '#9ca3af']

export default function Analytics() {
  const { t } = useTranslation()
  const [events, setEvents] = useState<Event[]>([])
  const [statsMap, setStatsMap] = useState<Record<string, EventStats>>({})
  const [totalUsers, setTotalUsers] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [retryCount, setRetryCount] = useState(0)

  useEffect(() => {
    const load = async () => {
      setLoading(true)
      setError(false)
      try {
        const [evts, users] = await Promise.all([listEvents(), listUsers()])
        setEvents(evts)
        setTotalUsers(users.length)

        const statsEntries = await Promise.all(
          evts.map(async ev => {
            try {
              const s = await getEventStats(ev.id)
              return [ev.id, s] as const
            } catch {
              return null
            }
          })
        )
        const map: Record<string, EventStats> = {}
        for (const entry of statsEntries) {
          if (entry) map[entry[0]] = entry[1]
        }
        setStatsMap(map)
      } catch (err) {
        console.error('Failed to load analytics data:', err)
        setError(true)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [retryCount])

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-900" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="max-w-7xl mx-auto p-6 flex flex-col items-center justify-center min-h-[50vh] text-center animate-fade-in">
        <div className="bg-white rounded-2xl p-8 max-w-md w-full shadow-xl border border-gray-100">
          <div className="w-16 h-16 bg-red-50 text-red-500 rounded-2xl flex items-center justify-center mx-auto mb-6">
            <AlertTriangle className="w-8 h-8" />
          </div>
          <h1 className="text-xl font-bold text-gray-950 mb-2">{t('event.loadError')}</h1>
          <p className="text-sm text-gray-500 mb-6 leading-relaxed">
            Could not fetch analytics statistics from the server.
          </p>
          <button
            onClick={() => setRetryCount(prev => prev + 1)}
            className="w-full py-3 bg-blue-900 hover:bg-blue-800 text-white font-semibold rounded-xl shadow transition"
          >
            {t('common.retry')}
          </button>
        </div>
      </div>
    )
  }

  if (events.length === 0) {
    return (
      <div className="max-w-7xl mx-auto p-6 animate-fade-in">
        <h1 className="text-2xl font-bold text-gray-900 mb-6">{t('analytics.title')}</h1>
        <div className="bg-white rounded-2xl p-12 text-center shadow-sm border border-gray-100 flex flex-col items-center justify-center min-h-[40vh]">
          <Activity className="w-16 h-16 text-gray-300 mb-4" />
          <h2 className="text-xl font-semibold text-gray-900 mb-2">{t('event.noEvents')}</h2>
          <p className="text-sm text-gray-500 leading-relaxed max-w-md">
            Create an incident event in Event Management to start capturing and exploring safety report analytics.
          </p>
        </div>
      </div>
    )
  }

  const activeEvents = events.filter(e => e.status === 'active')
  const allStats = Object.values(statsMap)
  const avgReportRate = allStats.length > 0
    ? Math.round(allStats.reduce((s, st) => s + st.report_rate, 0) / allStats.length)
    : 0

  const eventBarData = events.map(ev => ({
    name: ev.title.substring(0, 15) + (ev.title.length > 15 ? '...' : ''),
    [t('status.safe')]: statsMap[ev.id]?.safe || 0,
    [t('status.need_help')]: statsMap[ev.id]?.need_help || 0,
    [t('status.unreported')]: statsMap[ev.id]?.unreported || 0,
  }))

  const totalSafe = allStats.reduce((s, st) => s + st.safe, 0)
  const totalHelp = allStats.reduce((s, st) => s + st.need_help, 0)
  const totalUnreported = allStats.reduce((s, st) => s + st.unreported, 0)
  const overallPie = [
    { name: t('status.safe'), value: totalSafe },
    { name: t('status.need_help'), value: totalHelp },
    { name: t('status.unreported'), value: totalUnreported },
  ]

  return (
    <div className="max-w-7xl mx-auto p-6 animate-fade-in">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">{t('analytics.title')}</h1>

      <div className="grid grid-cols-4 gap-4 mb-8">
        <div className="bg-white rounded-xl p-5 shadow-sm border flex items-center gap-4">
          <Activity className="w-10 h-10 text-blue-500" />
          <div>
            <p className="text-sm text-gray-500">{t('analytics.totalEvents')}</p>
            <p className="text-2xl font-bold">{events.length}</p>
          </div>
        </div>
        <div className="bg-white rounded-xl p-5 shadow-sm border flex items-center gap-4">
          <AlertTriangle className="w-10 h-10 text-red-500" />
          <div>
            <p className="text-sm text-gray-500">{t('analytics.activeEvents')}</p>
            <p className="text-2xl font-bold">{activeEvents.length}</p>
          </div>
        </div>
        <div className="bg-white rounded-xl p-5 shadow-sm border flex items-center gap-4">
          <TrendingUp className="w-10 h-10 text-green-500" />
          <div>
            <p className="text-sm text-gray-500">{t('analytics.avgReportRate')}</p>
            <p className="text-2xl font-bold">{avgReportRate}%</p>
          </div>
        </div>
        <div className="bg-white rounded-xl p-5 shadow-sm border flex items-center gap-4">
          <Users className="w-10 h-10 text-purple-500" />
          <div>
            <p className="text-sm text-gray-500">{t('analytics.totalEmployees')}</p>
            <p className="text-2xl font-bold">{totalUsers}</p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-6">
        <div className="bg-white rounded-xl p-6 shadow-sm border">
          <h2 className="text-lg font-semibold mb-4">{t('analytics.reportByEvent')}</h2>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={eventBarData}>
              <XAxis dataKey="name" tick={{ fontSize: 11 }} />
              <YAxis />
              <Tooltip />
              <Legend />
              <Bar dataKey={t('status.safe')} fill="#22c55e" stackId="a" />
              <Bar dataKey={t('status.need_help')} fill="#ef4444" stackId="a" />
              <Bar dataKey={t('status.unreported')} fill="#9ca3af" stackId="a" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-white rounded-xl p-6 shadow-sm border">
          <h2 className="text-lg font-semibold mb-4">{t('analytics.overallDistribution')}</h2>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie data={overallPie} cx="50%" cy="50%" innerRadius={60} outerRadius={110} paddingAngle={3} dataKey="value" label={({ name, value }) => `${name}: ${value}`}>
                {overallPie.map((_, idx) => (
                  <Cell key={idx} fill={COLORS[idx]} />
                ))}
              </Pie>
              <Tooltip />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  )
}
