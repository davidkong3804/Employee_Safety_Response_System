import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './contexts/AuthContext'
import Navbar from './components/Navbar'
import ProtectedRoute from './components/ProtectedRoute'
import ReminderBanner from './components/ReminderBanner'
import Login from './pages/Login'
import Home from './pages/employee/Home'
import ReportPage from './pages/employee/ReportPage'
import Dashboard from './pages/manager/Dashboard'
import EventManagement from './pages/admin/EventManagement'
import UserManagement from './pages/admin/UserManagement'
import Analytics from './pages/admin/Analytics'

export default function App() {
  const { user } = useAuth()

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />
      <ReminderBanner />
      <Routes>
        <Route path="/login" element={user ? <Navigate to="/" replace /> : <Login />} />

        <Route path="/" element={
          <ProtectedRoute><Home /></ProtectedRoute>
        } />

        <Route path="/events/:eventId/report" element={
          <ProtectedRoute><ReportPage /></ProtectedRoute>
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
