import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import toast from 'react-hot-toast'
import { Shield } from 'lucide-react'
import { useAuth } from '../contexts/AuthContext'

export default function Login() {
  const { t } = useTranslation()
  const { login } = useAuth()
  const navigate = useNavigate()
  const [employeeId, setEmployeeId] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    try {
      const me = await login(employeeId, password)
      if (me.role === 'admin') navigate('/admin/events')
      else if (me.role === 'manager') navigate('/dashboard')
      else navigate('/')
    } catch {
      toast.error(t('login.error'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-900 to-blue-700">
      <div className="bg-white rounded-2xl shadow-2xl p-8 w-full max-w-md">
        <div className="text-center mb-8">
          <Shield className="w-16 h-16 text-blue-900 mx-auto mb-4" />
          <h1 className="text-2xl font-bold text-gray-900">{t('login.title')}</h1>
          <p className="text-gray-500 text-sm mt-1">Employee Safety & Response System</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">{t('login.employeeId')}</label>
            <input
              type="text"
              value={employeeId}
              onChange={(e) => setEmployeeId(e.target.value)}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="A001 / M001 / E001"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">{t('login.password')}</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="password123"
              required
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 bg-blue-900 text-white rounded-lg font-medium hover:bg-blue-800 transition disabled:opacity-50"
          >
            {loading ? '...' : t('login.submit')}
          </button>
        </form>

        <div className="mt-6 p-4 bg-gray-50 rounded-lg text-xs text-gray-500">
          <p className="font-medium mb-1">Demo Accounts (password: password123)</p>
          <p>Admin: A001 | Manager: M001 | Employee: E001</p>
        </div>
      </div>
    </div>
  )
}
