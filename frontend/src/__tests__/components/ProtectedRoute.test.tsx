import { render, screen } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { describe, it, expect, vi } from 'vitest'
import ProtectedRoute from '../../components/ProtectedRoute'
import * as AuthContextModule from '../../contexts/AuthContext'
import type { User } from '../../types'

const mockAdminUser: User = {
  id: 'uuid-1',
  employee_id: 'A001',
  name: 'Admin',
  email: 'admin@example.com',
  role: 'admin',
  department: 'IT',
  facility: 'Fab14',
  phone: null,
}

function renderRoute(
  user: User | null,
  loading = false,
  roles?: string[]
) {
  vi.spyOn(AuthContextModule, 'useAuth').mockReturnValue({
    user,
    loading,
    login: vi.fn(),
    logout: vi.fn(),
  })

  return render(
    <MemoryRouter initialEntries={['/protected']}>
      <Routes>
        <Route
          path="/protected"
          element={
            <ProtectedRoute roles={roles}>
              <div>Protected Content</div>
            </ProtectedRoute>
          }
        />
        <Route path="/login" element={<div>Login Page</div>} />
        <Route path="/" element={<div>Home Page</div>} />
      </Routes>
    </MemoryRouter>
  )
}

describe('ProtectedRoute', () => {
  it('shows spinner while loading', () => {
    renderRoute(null, true)
    expect(document.querySelector('.animate-spin')).toBeInTheDocument()
  })

  it('redirects to /login when user is null', () => {
    renderRoute(null, false)
    expect(screen.getByText('Login Page')).toBeInTheDocument()
  })

  it('renders children when user is authenticated', () => {
    renderRoute(mockAdminUser, false)
    expect(screen.getByText('Protected Content')).toBeInTheDocument()
  })

  it('redirects to / when role is not permitted', () => {
    const employeeUser: User = { ...mockAdminUser, role: 'employee' }
    renderRoute(employeeUser, false, ['admin', 'manager'])
    expect(screen.getByText('Home Page')).toBeInTheDocument()
  })

  it('renders children when role is in allowed list', () => {
    renderRoute(mockAdminUser, false, ['admin'])
    expect(screen.getByText('Protected Content')).toBeInTheDocument()
  })

  it('renders children when no roles restriction is set', () => {
    const employeeUser: User = { ...mockAdminUser, role: 'employee' }
    renderRoute(employeeUser, false)
    expect(screen.getByText('Protected Content')).toBeInTheDocument()
  })
})
