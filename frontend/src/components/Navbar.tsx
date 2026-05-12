import { Link, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Shield, LogOut, Globe } from 'lucide-react'
import { useAuth } from '../contexts/AuthContext'

export default function Navbar() {
  const { user, logout } = useAuth()
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()

  if (!user) return null

  const toggleLang = () => {
    i18n.changeLanguage(i18n.language === 'zh-TW' ? 'en' : 'zh-TW')
  }

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <nav className="bg-blue-900 text-white shadow-lg">
      <div className="max-w-7xl mx-auto px-4">
        <div className="flex items-center justify-between h-16">
          <div className="flex items-center gap-2">
            <Shield className="w-6 h-6 text-yellow-400" />
            <Link to="/" className="font-bold text-lg">{t('app.title')}</Link>
          </div>

          <div className="flex items-center gap-4">
            {user.role === 'employee' && (
              <Link to="/home" className="hover:text-yellow-300 transition">{t('nav.home')}</Link>
            )}

            {(user.role === 'manager' || user.role === 'admin') && (
              <Link to="/dashboard" className="hover:text-yellow-300 transition">{t('nav.dashboard')}</Link>
            )}

            {user.role === 'admin' && (
              <>
                <Link to="/admin/events" className="hover:text-yellow-300 transition">{t('nav.events')}</Link>
                <Link to="/admin/users" className="hover:text-yellow-300 transition">{t('nav.users')}</Link>
              </>
            )}

            <button onClick={toggleLang} className="flex items-center gap-1 hover:text-yellow-300 transition">
              <Globe className="w-4 h-4" />
              {i18n.language === 'zh-TW' ? 'EN' : '中文'}
            </button>

            <div className="flex items-center gap-2 ml-4 pl-4 border-l border-blue-700">
              <span className="text-sm text-blue-200">
                {user.name} ({user.role})
              </span>
              <button onClick={handleLogout} className="hover:text-yellow-300 transition" title={t('nav.logout')}>
                <LogOut className="w-5 h-5" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </nav>
  )
}
