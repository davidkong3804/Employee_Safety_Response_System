import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import UserManagement from '../../pages/admin/UserManagement'
import * as usersApi from '../../api/users'
import type { UserFull } from '../../types'

vi.mock('../../api/users', () => ({
  listUsers: vi.fn(),
  createUser: vi.fn(),
  updateUser: vi.fn(),
  deleteUser: vi.fn(),
}))

vi.mock('react-hot-toast', () => ({
  default: { success: vi.fn(), error: vi.fn() },
}))

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, params?: Record<string, unknown>) => {
      if (!params) return key
      return key + ':' + Object.values(params).join(',')
    },
  }),
}))

const mockedList = vi.mocked(usersApi.listUsers)
const mockedCreate = vi.mocked(usersApi.createUser)
const mockedDelete = vi.mocked(usersApi.deleteUser)

function makeUser(overrides: Partial<UserFull> = {}): UserFull {
  return {
    id: 'u-1',
    employee_id: 'E001',
    name: 'Test Employee',
    email: 't@example.com',
    role: 'employee',
    department: 'Engineering',
    facility: 'Fab14',
    phone: '0912345678',
    manager_id: null,
    is_active: true,
    ...overrides,
  }
}

describe('UserManagement', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    vi.spyOn(window, 'confirm').mockImplementation(() => true)
  })

  it('shows the spinner until listUsers resolves', async () => {
    let resolve: (us: UserFull[]) => void = () => {}
    mockedList.mockImplementation(() => new Promise((r) => { resolve = r }))
    const { container } = render(<UserManagement />)
    expect(container.querySelector('.animate-spin')).not.toBeNull()
    resolve([])
    await waitFor(() => expect(container.querySelector('.animate-spin')).toBeNull())
  })

  it('renders rows for each user', async () => {
    mockedList.mockResolvedValue([
      makeUser({ id: 'a', employee_id: 'E100', name: 'Alice' }),
      makeUser({ id: 'b', employee_id: 'E200', name: 'Bob', is_active: false }),
    ])
    const { container } = render(<UserManagement />)
    await waitFor(() => {
      const table = container.querySelector('table')!
      expect(within(table).getByText('Alice')).toBeInTheDocument()
      expect(within(table).getByText('Bob')).toBeInTheDocument()
    })
  })

  it('refetches with role filter when the role select changes', async () => {
    mockedList.mockResolvedValue([])
    render(<UserManagement />)
    await waitFor(() => expect(mockedList).toHaveBeenCalledTimes(1))
    expect(mockedList).toHaveBeenLastCalledWith(undefined)

    // Trigger filter change.
    const select = document.querySelector('select') as HTMLSelectElement
    fireEvent.change(select, { target: { value: 'admin' } })
    await waitFor(() => expect(mockedList).toHaveBeenCalledTimes(2))
    expect(mockedList).toHaveBeenLastCalledWith({ role: 'admin' })
  })

  it('opens the modal, submits the form, and refetches on success', async () => {
    mockedList.mockResolvedValueOnce([])
    mockedCreate.mockResolvedValue(makeUser() as unknown as UserFull)
    mockedList.mockResolvedValueOnce([makeUser({ name: 'Created' })])

    render(<UserManagement />)
    await waitFor(() => expect(mockedList).toHaveBeenCalledTimes(1))

    // Click "user.create" button (the one in the header, not the modal one).
    const createBtns = screen.getAllByText('user.create')
    fireEvent.click(createBtns[0])

    // Fill required inputs by placeholder.
    const empIdInput = screen.getByPlaceholderText('login.employeeId') as HTMLInputElement
    const nameInput = screen.getByPlaceholderText('user.name') as HTMLInputElement
    const emailInput = screen.getByPlaceholderText('user.email') as HTMLInputElement
    fireEvent.change(empIdInput, { target: { value: 'E999' } })
    fireEvent.change(nameInput, { target: { value: 'NewGuy' } })
    fireEvent.change(emailInput, { target: { value: 'new@example.com' } })

    fireEvent.submit(document.querySelector('form')!)
    await waitFor(() => expect(mockedCreate).toHaveBeenCalledTimes(1))
    expect(mockedCreate).toHaveBeenCalledWith(
      expect.objectContaining({ employee_id: 'E999', name: 'NewGuy', email: 'new@example.com' }),
    )
    await waitFor(() => expect(mockedList).toHaveBeenCalledTimes(2))
  })

  it('deactivates a user via deleteUser after confirmation', async () => {
    mockedList.mockResolvedValueOnce([makeUser({ id: 'kill-me', is_active: true })])
    mockedDelete.mockResolvedValue(undefined as unknown as void)
    mockedList.mockResolvedValueOnce([])

    const { container } = render(<UserManagement />)
    await waitFor(() => {
      expect(within(container.querySelector('table')!).getByText('Test Employee')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByText('user.inactive'))
    expect(window.confirm).toHaveBeenCalled()
    await waitFor(() => expect(mockedDelete).toHaveBeenCalledWith('kill-me'))
  })

  it('does not call deleteUser when confirmation is denied', async () => {
    vi.spyOn(window, 'confirm').mockReturnValueOnce(false)
    mockedList.mockResolvedValue([makeUser({ id: 'safe', is_active: true })])

    const { container } = render(<UserManagement />)
    await waitFor(() => {
      expect(within(container.querySelector('table')!).getByText('Test Employee')).toBeInTheDocument()
    })
    fireEvent.click(screen.getByText('user.inactive'))
    expect(mockedDelete).not.toHaveBeenCalled()
  })

  it('formats Taiwan mobile phone numbers in the table', async () => {
    mockedList.mockResolvedValue([
      makeUser({ phone: '0912345678' }),
    ])
    const { container } = render(<UserManagement />)
    await waitFor(() => {
      expect(within(container.querySelector('table')!).getByText('0912-345-678')).toBeInTheDocument()
    })
  })

  it('shows the "no users" placeholder when the list is empty', async () => {
    mockedList.mockResolvedValue([])
    render(<UserManagement />)
    await waitFor(() => {
      expect(screen.getByText('user.noUsers')).toBeInTheDocument()
    })
  })
})
