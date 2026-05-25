import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import toast from 'react-hot-toast'
import Login from '../../pages/Login'
import * as AuthContextModule from '../../contexts/AuthContext'
import type { User } from '../../types'

// --- mocks ---------------------------------------------------
const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useNavigate: () => mockNavigate }
})

vi.mock('react-hot-toast', () => ({
  default: { success: vi.fn(), error: vi.fn() },
}))

// --- helpers -------------------------------------------------
function makeUser(role: 'employee' | 'manager' | 'admin'): User {
  return {
    id: 'u-1',
    employee_id: role === 'admin' ? 'A001' : role === 'manager' ? 'M001' : 'E001',
    name: 'Test',
    email: 't@example.com',
    role,
    department: 'Engineering',
    facility: 'Fab14',
    phone: null,
  }
}

function renderLogin(loginImpl: (id: string, pw: string) => Promise<User>) {
  vi.spyOn(AuthContextModule, 'useAuth').mockReturnValue({
    user: null,
    loading: false,
    login: loginImpl,
    logout: vi.fn(),
  })
  return render(
    <MemoryRouter>
      <Login />
    </MemoryRouter>,
  )
}

async function submitForm(employeeId: string, password: string) {
  // The Login form's <label> is a sibling, not a wrapper, with no htmlFor,
  // so getByLabelText cannot associate them. Use placeholder as the handle.
  fireEvent.change(screen.getByPlaceholderText('A001 / M001 / E001'), {
    target: { value: employeeId },
  })
  fireEvent.change(screen.getByPlaceholderText('password123'), {
    target: { value: password },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Login' }))
}

// --- tests ---------------------------------------------------
describe('Login page', () => {
  beforeEach(() => vi.clearAllMocks())

  describe('rendering', () => {
    it('renders Employee ID + Password fields and a Login button', () => {
      renderLogin(vi.fn())
      expect(screen.getByPlaceholderText('A001 / M001 / E001')).toBeInTheDocument()
      expect(screen.getByPlaceholderText('password123')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Login' })).toBeInTheDocument()
      // Labels are present as visual text (not associated via htmlFor):
      expect(screen.getByText('Employee ID')).toBeInTheDocument()
      expect(screen.getByText('Password')).toBeInTheDocument()
    })
  })

  describe('role-based redirect after login', () => {
    it('admin → /admin/events', async () => {
      const login = vi.fn().mockResolvedValue(makeUser('admin'))
      renderLogin(login)
      await submitForm('A001', 'password123')
      await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith('/admin/events'))
    })

    it('manager → /dashboard', async () => {
      const login = vi.fn().mockResolvedValue(makeUser('manager'))
      renderLogin(login)
      await submitForm('M001', 'password123')
      await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith('/dashboard'))
    })

    it('employee → /', async () => {
      const login = vi.fn().mockResolvedValue(makeUser('employee'))
      renderLogin(login)
      await submitForm('E001', 'password123')
      await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith('/'))
    })
  })

  describe('login error handling', () => {
    it('shows error toast and does not navigate when login fails', async () => {
      const login = vi.fn().mockRejectedValue(new Error('401'))
      renderLogin(login)
      await submitForm('A001', 'wrong')
      await waitFor(() =>
        expect(toast.error).toHaveBeenCalledWith('Invalid employee ID or password'),
      )
      expect(mockNavigate).not.toHaveBeenCalled()
    })
  })

  describe('credentials forwarding', () => {
    it('calls login() with the typed credentials', async () => {
      const login = vi.fn().mockResolvedValue(makeUser('employee'))
      renderLogin(login)
      await submitForm('E001', 'mypassword')
      expect(login).toHaveBeenCalledWith('E001', 'mypassword')
    })
  })
})
