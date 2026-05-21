import { useEffect, useState, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import { RefreshCw, Bell, Search } from 'lucide-react'
import toast from 'react-hot-toast'
import { listEvents } from '../../api/events'
import { getEventStats, getStatsByDepartment, getTeamStatus, triggerReminders } from '../../api/reports'
import StatusBadge from '../../components/StatusBadge'
import type { Event, EventStats, DepartmentStats, SafetyReport } from '../../types'

const COLORS = { safe: '#22c55e', need_help: '#ef4444', unreported: '#9ca3af' }

export default function Dashboard() {
  const { t } = useTranslation()
  const [events, setEvents] = useState<Event[]>([])
  const [selectedEventId, setSelectedEventId] = useState<string>('')
  const [stats, setStats] = useState<EventStats | null>(null)
  const [deptStats, setDeptStats] = useState<DepartmentStats[]>([])
  const [reports, setReports] = useState<SafetyReport[]>([])
  const [filterFacility, setFilterFacility] = useState('')
  const [filterDept, setFilterDept] = useState('')
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)

  useEffect(() => {
    listEvents().then(evts => {
      setEvents(evts)
      const active = evts.find(e => e.status === 'active')
      if (active) setSelectedEventId(active.id)
    }).finally(() => setLoading(false))
  }, [])

  const loadData = useCallback(async () => {
    if (!selectedEventId) return
    setRefreshing(true)
    try {
      const [s, ds, rpts] = await Promise.all([
        getEventStats(selectedEventId),
        getStatsByDepartment(selectedEventId),
        getTeamStatus(selectedEventId),
      ])
      setStats(s)
      setDeptStats(ds)
      setReports(rpts)
    } finally {
      setRefreshing(false)
    }
  }, [selectedEventId])

  useEffect(() => { loadData() }, [loadData])

  // Auto-refresh every 30 seconds
  useEffect(() => {
    if (!selectedEventId) return
    const interval = setInterval(loadData, 30000)
    return () => clearInterval(interval)
  }, [selectedEventId, loadData])

  const handleRemind = async () => {
    if (!selectedEventId) return
    try {
      const result = await triggerReminders(selectedEventId)
      toast.success(t('dashboard.reminded', { count: result.reminded_count }))
    } catch {
      toast.error(t('dashboard.remindFailed'))
    }
  }

  const filteredReports = reports.filter(r => {
    if (filterFacility && r.facility !== filterFacility) return false
    if (filterDept && r.department !== filterDept) return false
    return true
  })

  const facilities = [...new Set(reports.map(r => r.facility).filter(Boolean))]
  const departments = [...new Set(reports.map(r => r.department).filter(Boolean))]

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-900" />
      </div>
    )
  }

  const pieData = stats ? [
    { name: t('status.safe'), value: stats.safe, color: COLORS.safe },
    { name: t('status.need_help'), value: stats.need_help, color: COLORS.need_help },
    { name: t('status.unreported'), value: stats.unreported, color: COLORS.unreported },
  ] : []

  const barData = deptStats.map(d => ({
    name: d.department,
    [t('status.safe')]: d.safe,
    [t('status.need_help')]: d.need_help,
    [t('status.unreported')]: d.unreported,
  }))

  return (
    <div className="max-w-7xl mx-auto p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">{t('dashboard.title')}</h1>
        <div className="flex items-center gap-3">
          <select
            value={selectedEventId}
            onChange={e => setSelectedEventId(e.target.value)}
            className="px-3 py-2 border border-gray-300 rounded-lg"
          >
            {events.map(ev => (
              <option key={ev.id} value={ev.id}>{ev.title}</option>
            ))}
          </select>
          <button onClick={loadData} className="p-2 hover:bg-gray-100 rounded-lg" title="Refresh">
            <RefreshCw className={`w-5 h-5 ${refreshing ? 'animate-spin' : ''}`} />
          </button>
          <button onClick={handleRemind} className="flex items-center gap-2 px-4 py-2 bg-orange-500 text-white rounded-lg hover:bg-orange-600 transition">
            <Bell className="w-4 h-4" />
            {t('dashboard.remind')}
          </button>
        </div>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-4 gap-4 mb-8">
          <div className="bg-white rounded-xl p-5 shadow-sm border">
            <p className="text-sm text-gray-500">{t('dashboard.total')}</p>
            <p className="text-3xl font-bold text-gray-900">{stats.total}</p>
          </div>
          <div className="bg-green-50 rounded-xl p-5 shadow-sm border border-green-200">
            <p className="text-sm text-green-600">{t('status.safe')}</p>
            <p className="text-3xl font-bold text-green-700">{stats.safe}</p>
          </div>
          <div className="bg-red-50 rounded-xl p-5 shadow-sm border border-red-200">
            <p className="text-sm text-red-600">{t('status.need_help')}</p>
            <p className="text-3xl font-bold text-red-700">{stats.need_help}</p>
          </div>
          <div className="bg-gray-50 rounded-xl p-5 shadow-sm border border-gray-200">
            <p className="text-sm text-gray-500">{t('status.unreported')}</p>
            <p className="text-3xl font-bold text-gray-700">{stats.unreported}</p>
            <p className="text-sm text-blue-600 mt-1">{t('dashboard.reportRate')}: {stats.report_rate}%</p>
          </div>
        </div>
      )}

      {/* Charts */}
      <div className="grid grid-cols-2 gap-6 mb-8">
        <div className="bg-white rounded-xl p-6 shadow-sm border">
          <h2 className="text-lg font-semibold mb-4">{t('dashboard.reportRate')}</h2>
          <ResponsiveContainer width="100%" height={280}>
            <PieChart>
              <Pie data={pieData} cx="50%" cy="50%" innerRadius={60} outerRadius={100} paddingAngle={3} dataKey="value" label={({ name, value }) => `${name}: ${value}`}>
                {pieData.map((entry, idx) => (
                  <Cell key={idx} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-white rounded-xl p-6 shadow-sm border">
          <h2 className="text-lg font-semibold mb-4">{t('dashboard.byDepartment')}</h2>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={barData}>
              <XAxis dataKey="name" tick={{ fontSize: 12 }} />
              <YAxis />
              <Tooltip />
              <Legend />
              <Bar dataKey={t('status.safe')} fill={COLORS.safe} stackId="a" />
              <Bar dataKey={t('status.need_help')} fill={COLORS.need_help} stackId="a" />
              <Bar dataKey={t('status.unreported')} fill={COLORS.unreported} stackId="a" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Filters + Employee List */}
      <div className="bg-white rounded-xl shadow-sm border">
        <div className="p-4 border-b flex items-center gap-4">
          <h2 className="text-lg font-semibold">{t('dashboard.employeeList')}</h2>
          <div className="flex items-center gap-2 ml-auto">
            <Search className="w-4 h-4 text-gray-400" />
            <select value={filterFacility} onChange={e => setFilterFacility(e.target.value)} className="px-2 py-1 border rounded text-sm">
              <option value="">{t('dashboard.facility')}: {t('dashboard.all')}</option>
              {facilities.map(f => <option key={f} value={f!}>{f}</option>)}
            </select>
            <select value={filterDept} onChange={e => setFilterDept(e.target.value)} className="px-2 py-1 border rounded text-sm">
              <option value="">{t('dashboard.department')}: {t('dashboard.all')}</option>
              {departments.map(d => <option key={d} value={d!}>{d}</option>)}
            </select>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50 text-left text-sm text-gray-500">
              <tr>
                <th className="px-4 py-3">ID</th>
                <th className="px-4 py-3">{t('user.name')}</th>
                <th className="px-4 py-3">{t('user.department')}</th>
                <th className="px-4 py-3">{t('user.facility')}</th>
                <th className="px-4 py-3">{t('common.status')}</th>
                <th className="px-4 py-3">{t('user.phone')}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {filteredReports.map(r => (
                <tr key={r.id} className={
                  r.status === 'need_help' ? 'bg-red-50' :
                  r.status === null ? 'bg-yellow-50' : ''
                }>
                  <td className="px-4 py-3 text-sm font-mono">{r.employee_id}</td>
                  <td className="px-4 py-3 font-medium">{r.user_name}</td>
                  <td className="px-4 py-3 text-sm">{r.department}</td>
                  <td className="px-4 py-3 text-sm">{r.facility}</td>
                  <td className="px-4 py-3"><StatusBadge status={r.status} /></td>
                  <td className="px-4 py-3 text-sm text-gray-500">{r.phone}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
