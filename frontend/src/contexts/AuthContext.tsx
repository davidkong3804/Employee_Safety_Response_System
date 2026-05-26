import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { getMe, login as apiLogin } from '../api/auth'
import type { User } from '../types'

interface AuthContextType {
  user: User | null
  loading: boolean
  login: (employeeId: string, password: string) => Promise<User>
  logout: () => void
}

const AuthContext = createContext<AuthContextType>(null!)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const token = localStorage.getItem('token')
    if (token) {
      getMe()
        .then(setUser)
        .catch(() => localStorage.removeItem('token'))
        .finally(() => setLoading(false))
    } else {
      setLoading(false)
    }
  }, [])

  const login = async (employeeId: string, password: string): Promise<User> => {
    const { access_token } = await apiLogin(employeeId, password)
    localStorage.setItem('token', access_token)
    // Flag so the next visit to Home shows the reminder modal once (if the
    // user has unreported reminders). Cleared by Home after it shows, or by
    // logout. sessionStorage is per-tab so a fresh tab gets a fresh modal.
    sessionStorage.setItem('reminder-modal-pending', '1')
    const me = await getMe()
    setUser(me)
    return me
  }

  const logout = () => {
    localStorage.removeItem('token')
    sessionStorage.removeItem('reminder-modal-pending')
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
