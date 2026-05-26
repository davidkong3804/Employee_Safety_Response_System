export interface User {
  id: string
  employee_id: string
  name: string
  email: string
  role: 'employee' | 'manager' | 'admin'
  department: string | null
  facility: string | null
  phone: string | null
}

export interface Event {
  id: string
  title: string
  description: string | null
  event_type: string
  severity: string
  status: 'active' | 'closed'
  facility: string[] | null
  created_by: string
  created_at: string
  closed_at: string | null
}

export interface SafetyReport {
  id: string
  event_id: string
  user_id: string
  user_name: string
  employee_id: string
  department: string | null
  facility: string | null
  phone: string | null
  status: 'safe' | 'need_help' | null
  message: string | null
  reported_at: string | null
}

export interface EventStats {
  total: number
  safe: number
  need_help: number
  unreported: number
  report_rate: number
}

export interface DepartmentStats {
  department: string
  total: number
  safe: number
  need_help: number
  unreported: number
}

export interface PaginatedReports {
  items: SafetyReport[]
  total: number
  limit: number
  offset: number
}

export interface UserFull {
  id: string
  employee_id: string
  name: string
  email: string
  role: string
  department: string | null
  facility: string | null
  phone: string | null
  manager_id: string | null
  is_active: boolean
}
