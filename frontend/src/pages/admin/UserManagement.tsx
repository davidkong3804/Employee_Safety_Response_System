import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import toast from 'react-hot-toast'
import { Plus, X } from 'lucide-react'
import { listUsers, createUser, deleteUser } from '../../api/users'
import type { UserFull } from '../../types'

export default function UserManagement() {
  const { t } = useTranslation()
  const [users, setUsers] = useState<UserFull[]>([])
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [filterRole, setFilterRole] = useState('')
  const [form, setForm] = useState({
    employee_id: '', name: '', email: '', password: 'password123',
    role: 'employee', department: '', facility: '', phone: '',
  })

  // Returns the underlying promise so callers (e.g. handleCreate) can
  // `await load()` and only act after the refetch lands.
  const load = () => {
    return listUsers(filterRole ? { role: filterRole } : undefined).then(setUsers).finally(() => setLoading(false))
  }

  useEffect(() => { void load() }, [filterRole])

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    if (submitting) return
    setSubmitting(true)
    try {
      await createUser(form)
      toast.success(t('user.createSuccess'))
      // Refetch BEFORE closing the modal so the new user is already in
      // the table when the dialog dismisses — no flicker.
      await load()
      setShowCreate(false)
    } catch {
      toast.error(t('user.createFailed'))
    } finally {
      setSubmitting(false)
    }
  }

  const handleDeactivate = async (id: string) => {
    if (!window.confirm(t('user.deactivateConfirm'))) return
    try {
      await deleteUser(id)
      toast.success(t('user.deactivateSuccess'))
      load()
    } catch {
      toast.error(t('user.deactivateFailed'))
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-900" />
      </div>
    )
  }

  return (
    <div className="max-w-6xl mx-auto p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">{t('nav.users')}</h1>
        <div className="flex items-center gap-3">
          <select value={filterRole} onChange={e => setFilterRole(e.target.value)} className="px-3 py-2 border rounded-lg text-sm">
            <option value="">{t('user.role')}: {t('dashboard.all')}</option>
            <option value="admin">{t('user.roles.admin')}</option>
            <option value="manager">{t('user.roles.manager')}</option>
            <option value="employee">{t('user.roles.employee')}</option>
          </select>
          <button onClick={() => setShowCreate(true)} className="flex items-center gap-2 px-4 py-2 bg-blue-900 text-white rounded-lg hover:bg-blue-800 transition">
            <Plus className="w-4 h-4" />
            {t('user.create')}
          </button>
        </div>
      </div>

      {showCreate && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-6 w-full max-w-lg">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-bold">{t('user.create')}</h2>
              <button onClick={() => setShowCreate(false)}><X className="w-5 h-5" /></button>
            </div>
            <form onSubmit={handleCreate} className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <input value={form.employee_id} onChange={e => setForm({...form, employee_id: e.target.value})} placeholder={t('login.employeeId')} className="px-3 py-2 border rounded-lg" required />
                <input value={form.name} onChange={e => setForm({...form, name: e.target.value})} placeholder={t('user.name')} className="px-3 py-2 border rounded-lg" required />
                <input value={form.email} onChange={e => setForm({...form, email: e.target.value})} placeholder={t('user.email')} className="px-3 py-2 border rounded-lg" required type="email" />
                <select value={form.role} onChange={e => setForm({...form, role: e.target.value})} className="px-3 py-2 border rounded-lg">
                  <option value="employee">{t('user.roles.employee')}</option>
                  <option value="manager">{t('user.roles.manager')}</option>
                  <option value="admin">{t('user.roles.admin')}</option>
                </select>
                <input value={form.department} onChange={e => setForm({...form, department: e.target.value})} placeholder={t('user.department')} className="px-3 py-2 border rounded-lg" />
                <input value={form.facility} onChange={e => setForm({...form, facility: e.target.value})} placeholder={t('user.facility')} className="px-3 py-2 border rounded-lg" />
                <input value={form.phone} onChange={e => setForm({...form, phone: e.target.value})} placeholder={t('user.phone')} className="px-3 py-2 border rounded-lg" />
                <input value={form.password} onChange={e => setForm({...form, password: e.target.value})} placeholder={t('login.password')} className="px-3 py-2 border rounded-lg" type="password" />
              </div>
              <button
                type="submit"
                disabled={submitting}
                className="w-full py-2 bg-blue-900 text-white rounded-lg hover:bg-blue-800 transition disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {submitting ? t('user.creating') : t('user.create')}
              </button>
            </form>
          </div>
        </div>
      )}

      <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50 text-left text-sm text-gray-500">
            <tr>
              <th className="px-4 py-3 whitespace-nowrap">ID</th>
              <th className="px-4 py-3 whitespace-nowrap">{t('user.name')}</th>
              <th className="px-4 py-3 whitespace-nowrap">{t('user.email')}</th>
              <th className="px-4 py-3 whitespace-nowrap">{t('user.role')}</th>
              <th className="px-4 py-3 whitespace-nowrap">{t('user.department')}</th>
              <th className="px-4 py-3 whitespace-nowrap">{t('user.facility')}</th>
              <th className="px-4 py-3 whitespace-nowrap">{t('common.status')}</th>
              <th className="px-4 py-3 whitespace-nowrap">{t('common.actions')}</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {users.map(u => (
              <tr key={u.id} className={!u.is_active ? 'opacity-50' : ''}>
                <td className="px-4 py-3 text-sm font-mono">{u.employee_id}</td>
                <td className="px-4 py-3 font-medium">{u.name}</td>
                <td className="px-4 py-3 text-sm">{u.email}</td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                    u.role === 'admin' ? 'bg-purple-100 text-purple-800' :
                    u.role === 'manager' ? 'bg-blue-100 text-blue-800' :
                    'bg-gray-100 text-gray-800'
                  }`}>{u.role}</span>
                </td>
                <td className="px-4 py-3 text-sm">{u.department}</td>
                <td className="px-4 py-3 text-sm">{u.facility}</td>
                <td className="px-4 py-3">
                  <span className={`text-xs ${u.is_active ? 'text-green-600' : 'text-red-600'}`}>
                    {u.is_active ? t('user.active') : t('user.inactive')}
                  </span>
                </td>
                <td className="px-4 py-3">
                  {u.is_active && (
                    <button onClick={() => handleDeactivate(u.id)} className="text-xs px-2 py-1 bg-red-100 text-red-800 rounded hover:bg-red-200">
                      {t('user.inactive')}
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
