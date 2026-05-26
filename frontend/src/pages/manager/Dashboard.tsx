import { useCallback, useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import { RefreshCw, Bell, Search } from 'lucide-react'
import toast from 'react-hot-toast'
import { List, type RowComponentProps } from 'react-window'
import { listEvents } from '../../api/events'
import { getEventStats, getStatsByDepartment, getTeamStatus, triggerReminders, type TeamStatusParams } from '../../api/reports'
import StatusBadge from '../../components/StatusBadge'
import { useAuth } from '../../contexts/AuthContext'
import type { Event, EventStats, DepartmentStats, SafetyReport } from '../../types'

const COLORS = { safe: '#22c55e', need_help: '#ef4444', unreported: '#9ca3af' }
const PAGE_SIZE = 100
const ROW_HEIGHT = 56
const LIST_HEIGHT = 560
// Prefetch the next page when the viewport gets within this many rows of the
// bottom — keeps scrolling smooth without flashing an empty patch.
const LOAD_AHEAD = 20

type StatusFilter = '' | 'safe' | 'need_help' | 'unreported'

export default function Dashboard() {
  const { t } = useTranslation()
  const { user } = useAuth()
  const isAdmin = user?.role === 'admin'
  const [events, setEvents] = useState<Event[]>([])
  const [selectedEventId, setSelectedEventId] = useState<string>('')
  const [stats, setStats] = useState<EventStats | null>(null)
  const [deptStats, setDeptStats] = useState<DepartmentStats[]>([])
  const [reports, setReports] = useState<SafetyReport[]>([])
  const [total, setTotal] = useState(0)
  const [filterDept, setFilterDept] = useState('')
  const [filterStatus, setFilterStatus] = useState<StatusFilter>('')
  const [searchInput, setSearchInput] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const loadingMoreRef = useRef(false)

  // Debounce search box → 300ms after the user stops typing the actual
  // server-side query fires. Prevents one fetch per keystroke under load.
  useEffect(() => {
    const handle = setTimeout(() => setDebouncedSearch(searchInput.trim()), 300)
    return () => clearTimeout(handle)
  }, [searchInput])

  // Initial event list
  useEffect(() => {
    listEvents().then(evts => {
      setEvents(evts)
      const active = evts.find(e => e.status === 'active')
      if (active) setSelectedEventId(active.id)
    }).finally(() => setLoading(false))
  }, [])

  const buildQuery = useCallback((offset: number): TeamStatusParams => ({
    limit: PAGE_SIZE,
    offset,
    department: filterDept || undefined,
    status: filterStatus || undefined,
    search: debouncedSearch || undefined,
  }), [filterDept, filterStatus, debouncedSearch])

  // Fetch stats + dept aggregate + first page of the employee list. Called
  // when the event changes, a filter changes, or the user hits Refresh.
  const reloadAll = useCallback(async () => {
    if (!selectedEventId) return
    setRefreshing(true)
    try {
      const [s, ds, page] = await Promise.all([
        getEventStats(selectedEventId),
        getStatsByDepartment(selectedEventId),
        getTeamStatus(selectedEventId, buildQuery(0)),
      ])
      setStats(s)
      setDeptStats(ds)
      setReports(page.items)
      setTotal(page.total)
    } finally {
      setRefreshing(false)
    }
  }, [selectedEventId, buildQuery])

  useEffect(() => { reloadAll() }, [reloadAll])

  // 30s polling — refreshes KPI cards, dept chart, and the event list (so
  // a newly-created admin event shows up in the selector without F5). The
  // detailed employee list is intentionally left alone so the user's scroll
  // position and visible rows don't pop on every tick.
  useEffect(() => {
    if (!selectedEventId) return
    const tick = async () => {
      try {
        const [s, ds, evts] = await Promise.all([
          getEventStats(selectedEventId),
          getStatsByDepartment(selectedEventId),
          listEvents(),
        ])
        setStats(s)
        setDeptStats(ds)
        setEvents(evts)
      } catch {
        // swallow — next tick or manual refresh will retry
      }
    }
    const interval = setInterval(tick, 30000)
    return () => clearInterval(interval)
  }, [selectedEventId])

  // Append next page when the viewport approaches the loaded tail.
  const loadMore = useCallback(async () => {
    if (loadingMoreRef.current) return
    if (reports.length >= total) return
    loadingMoreRef.current = true
    try {
      const page = await getTeamStatus(selectedEventId, buildQuery(reports.length))
      setReports(prev => [...prev, ...page.items])
      setTotal(page.total)
    } finally {
      loadingMoreRef.current = false
    }
  }, [selectedEventId, reports.length, total, buildQuery])

  const handleRemind = async () => {
    if (!selectedEventId) return
    try {
      const result = await triggerReminders(selectedEventId)
      toast.success(t('dashboard.reminded', { count: result.reminded_count }))
    } catch {
      toast.error(t('dashboard.remindFailed'))
    }
  }

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
          <button onClick={reloadAll} className="p-2 hover:bg-gray-100 rounded-lg" title={t('dashboard.refresh')}>
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

      {/* Filters + virtualized employee list */}
      <div className="bg-white rounded-xl shadow-sm border">
        <div className="p-4 border-b flex flex-wrap items-center gap-3">
          <h2 className="text-lg font-semibold">{t('dashboard.employeeList')}</h2>
          <span className="text-sm text-gray-500">
            {t('dashboard.showing', { shown: reports.length, total })}
          </span>
          <div className="flex items-center gap-2 ml-auto">
            <div className="relative">
              <Search className="w-4 h-4 text-gray-400 absolute left-2 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={searchInput}
                onChange={e => setSearchInput(e.target.value)}
                placeholder={t('dashboard.searchPlaceholder')}
                className="pl-7 pr-2 py-1 border rounded text-sm w-48"
              />
            </div>
            {isAdmin && (
              <select value={filterDept} onChange={e => setFilterDept(e.target.value)} className="px-2 py-1 border rounded text-sm">
                <option value="">{t('dashboard.department')}: {t('dashboard.all')}</option>
                {deptStats.map(d => (
                  <option key={d.department} value={d.department}>{d.department}</option>
                ))}
              </select>
            )}
            <select value={filterStatus} onChange={e => setFilterStatus(e.target.value as StatusFilter)} className="px-2 py-1 border rounded text-sm">
              <option value="">{t('common.status')}: {t('dashboard.all')}</option>
              <option value="need_help">{t('status.need_help')}</option>
              <option value="unreported">{t('status.unreported')}</option>
              <option value="safe">{t('status.safe')}</option>
            </select>
          </div>
        </div>

        <ListHeader t={t} />

        <div style={{ height: LIST_HEIGHT }}>
          {reports.length === 0 ? (
            <div className="flex items-center justify-center h-full text-gray-400">
              {t('dashboard.noResults')}
            </div>
          ) : (
            <List
              rowCount={reports.length}
              rowHeight={ROW_HEIGHT}
              rowComponent={ReportRow}
              rowProps={{ reports }}
              overscanCount={8}
              onRowsRendered={({ stopIndex }) => {
                if (stopIndex >= reports.length - LOAD_AHEAD) {
                  loadMore()
                }
              }}
            />
          )}
        </div>
      </div>
    </div>
  )
}

function ListHeader({ t }: { t: (key: string) => string }) {
  return (
    <div className="grid grid-cols-[100px_minmax(120px,1fr)_minmax(120px,1fr)_100px_120px_140px] gap-3 px-4 py-3 bg-gray-50 text-left text-xs uppercase tracking-wide text-gray-500 border-b">
      <div>ID</div>
      <div>{t('user.name')}</div>
      <div>{t('user.department')}</div>
      <div>{t('user.facility')}</div>
      <div>{t('common.status')}</div>
      <div>{t('user.phone')}</div>
    </div>
  )
}

function ReportRow({
  index,
  style,
  reports,
}: RowComponentProps<{ reports: SafetyReport[] }>) {
  const r = reports[index]
  if (!r) return null
  const bg = r.status === 'need_help'
    ? 'bg-red-50'
    : r.status === null
      ? 'bg-yellow-50'
      : ''
  return (
    <div
      style={style}
      className={`grid grid-cols-[100px_minmax(120px,1fr)_minmax(120px,1fr)_100px_120px_140px] gap-3 px-4 items-center border-b border-gray-100 ${bg}`}
    >
      <div className="text-sm font-mono truncate">{r.employee_id}</div>
      <div className="font-medium truncate">{r.user_name}</div>
      <div className="text-sm truncate">{r.department}</div>
      <div className="text-sm truncate">{r.facility}</div>
      <div><StatusBadge status={r.status} /></div>
      <div className="text-sm text-gray-500 truncate">{r.phone}</div>
    </div>
  )
}

