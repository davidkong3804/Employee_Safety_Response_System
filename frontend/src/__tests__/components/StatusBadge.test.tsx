import { render, screen } from '@testing-library/react'
import { I18nextProvider } from 'react-i18next'
import i18n from 'i18next'
import { describe, it, expect } from 'vitest'
import StatusBadge from '../../components/StatusBadge'

const renderBadge = (status: 'safe' | 'need_help' | null, size?: 'sm' | 'md') =>
  render(
    <I18nextProvider i18n={i18n}>
      <StatusBadge status={status} size={size} />
    </I18nextProvider>
  )

describe('StatusBadge', () => {
  describe('safe status', () => {
    it('renders "Safe" label', () => {
      renderBadge('safe')
      expect(screen.getByText('Safe')).toBeInTheDocument()
    })

    it('applies green background classes', () => {
      renderBadge('safe')
      const el = screen.getByText('Safe')
      expect(el).toHaveClass('bg-green-100')
      expect(el).toHaveClass('text-green-800')
    })
  })

  describe('need_help status', () => {
    it('renders "Need Help" label', () => {
      renderBadge('need_help')
      expect(screen.getByText('Need Help')).toBeInTheDocument()
    })

    it('applies red background classes', () => {
      renderBadge('need_help')
      expect(screen.getByText('Need Help')).toHaveClass('bg-red-100')
    })
  })

  describe('null status (unreported)', () => {
    it('renders "Unreported" label', () => {
      renderBadge(null)
      expect(screen.getByText('Unreported')).toBeInTheDocument()
    })

    it('applies gray background classes', () => {
      renderBadge(null)
      expect(screen.getByText('Unreported')).toHaveClass('bg-gray-100')
    })
  })

  describe('size prop', () => {
    it('applies small padding by default', () => {
      renderBadge('safe')
      expect(screen.getByText('Safe')).toHaveClass('px-2', 'py-0.5', 'text-xs')
    })

    it('applies medium padding when size="md"', () => {
      renderBadge('safe', 'md')
      expect(screen.getByText('Safe')).toHaveClass('px-3', 'py-1.5', 'text-sm')
    })
  })

  it('renders a span element', () => {
    renderBadge('safe')
    expect(screen.getByText('Safe').tagName).toBe('SPAN')
  })
})
