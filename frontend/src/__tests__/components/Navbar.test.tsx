import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi } from 'vitest'
import Navbar from '../../components/Navbar'
import * as AuthContextModule from '../../contexts/AuthContext'
import type { User } from '../../types'

const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useNavigate: () => mockNavigate }
})

function makeUser(role: 'employee' | 'manager' | 'admin'): User {
  return {
    id: 'u-1',
    employee_id: 'X001',
    name: 'Test User',
    email: 't@example.com',
    role,
    department: 'Engineering',
    facility: 'Fab14',
    phone: null,
  }
}

function renderNavbar(user: User | null) {
  const logout = vi.fn()
  vi.spyOn(AuthContextModule, 'useAuth').mockReturnValue({
    user,
    loading: false,
    login: vi.fn(),
    logout,
  })
  const utils = render(
    <MemoryRouter>
      <Navbar />
    </MemoryRouter>,
  )
  return { logout, ...utils }
}

describe('Navbar', () => {
  describe('when not logged in', () => {
    it('renders nothing', () => {
      const { container } = renderNavbar(null)
      expect(container).toBeEmptyDOMElement()
    })
  })

  describe('role-based navigation links', () => {
    it('employee sees only Home (no Dashboard / Events / Users)', () => {
      renderNavbar(makeUser('employee'))
      expect(screen.getByText('Home')).toBeInTheDocument()
      expect(screen.queryByText('Dashboard')).not.toBeInTheDocument()
      expect(screen.queryByText('Event Management')).not.toBeInTheDocument()
      expect(screen.queryByText('User Management')).not.toBeInTheDocument()
    })

    it('manager sees Home + Dashboard but not Event/User Management', () => {
      renderNavbar(makeUser('manager'))
      expect(screen.getByText('Home')).toBeInTheDocument()
      expect(screen.getByText('Dashboard')).toBeInTheDocument()
      expect(screen.queryByText('Event Management')).not.toBeInTheDocument()
      expect(screen.queryByText('User Management')).not.toBeInTheDocument()
    })

    it('admin sees all four links', () => {
      renderNavbar(makeUser('admin'))
      expect(screen.getByText('Home')).toBeInTheDocument()
      expect(screen.getByText('Dashboard')).toBeInTheDocument()
      expect(screen.getByText('Event Management')).toBeInTheDocument()
      expect(screen.getByText('User Management')).toBeInTheDocument()
    })
  })

  describe('logout', () => {
    it('calls logout() then navigates to /login', () => {
      const { logout } = renderNavbar(makeUser('admin'))
      const logoutBtn = screen.getByTitle('Logout')
      fireEvent.click(logoutBtn)
      expect(logout).toHaveBeenCalled()
      expect(mockNavigate).toHaveBeenCalledWith('/login')
    })
  })

  describe('user info display', () => {
    it('shows name and role next to logout button', () => {
      renderNavbar(makeUser('admin'))
      expect(screen.getByText(/Test User \(admin\)/)).toBeInTheDocument()
    })
  })
})
