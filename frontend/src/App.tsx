import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './contexts/AuthContext'
import Navbar from './components/Navbar'
import ProtectedRoute from './components/ProtectedRoute'
import Login from './pages/Login'
import Home from './pages/employee/Home'
import ReportPage from './pages/employee/ReportPage'
import PeerStatus from './pages/employee/PeerStatus'
import Dashboard from './pages/manager/Dashboard'
import EventManagement from './pages/admin/EventManagement'
import UserManagement from './pages/admin/UserManagement'
import Analytics from './pages/admin/Analytics'

function RoleRedirect() {
  const { user, loading } = useAuth()
  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-900" />
      </div>
    )
  }
  if (!user) return <Navigate to="/login" replace />
  if (user.role === 'admin') return <Navigate to="/admin/events" replace />
  if (user.role === 'manager') return <Navigate to="/dashboard" replace />
  return <Navigate to="/home" replace />
}

export default function App() {
  const { user } = useAuth()

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />
      <Routes>
        <Route path="/login" element={user ? <Navigate to="/" replace /> : <Login />} />

        <Route path="/" element={<RoleRedirect />} />

        <Route path="/home" element={
          <ProtectedRoute roles={['employee']}><Home /></ProtectedRoute>
        } />

        <Route path="/report/:eventId" element={
          <ProtectedRoute><ReportPage /></ProtectedRoute>
        } />

        <Route path="/peers/:eventId" element={
          <ProtectedRoute><PeerStatus /></ProtectedRoute>
        } />

        <Route path="/dashboard" element={
          <ProtectedRoute roles={['manager', 'admin']}><Dashboard /></ProtectedRoute>
        } />

        <Route path="/admin/events" element={
          <ProtectedRoute roles={['admin']}><EventManagement /></ProtectedRoute>
        } />

        <Route path="/admin/users" element={
          <ProtectedRoute roles={['admin']}><UserManagement /></ProtectedRoute>
        } />

        <Route path="/admin/analytics" element={
          <ProtectedRoute roles={['admin']}><Analytics /></ProtectedRoute>
        } />

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </div>
  )
}
