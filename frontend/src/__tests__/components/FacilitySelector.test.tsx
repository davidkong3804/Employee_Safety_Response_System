import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import FacilitySelector from '../../components/FacilitySelector'

// Helper: render with onChange spy
function setup(initialValue: string[] = []) {
  const onChange = vi.fn()
  const utils = render(<FacilitySelector value={initialValue} onChange={onChange} />)
  return { onChange, ...utils }
}

describe('FacilitySelector', () => {
  describe('initial render', () => {
    it('shows the "All Facilities" master toggle', () => {
      setup([])
      expect(screen.getByText('All Facilities')).toBeInTheDocument()
    })

    it('renders all four country rows', () => {
      setup([])
      expect(screen.getByText('Taiwan')).toBeInTheDocument()
      expect(screen.getByText('United States')).toBeInTheDocument()
      expect(screen.getByText('Japan')).toBeInTheDocument()
      expect(screen.getByText('Germany')).toBeInTheDocument()
    })

    it('"All Facilities" is checked when value is empty', () => {
      setup([])
      const allCheckbox = screen.getByLabelText('All Facilities') as HTMLInputElement
      expect(allCheckbox.checked).toBe(true)
    })

    it('does not expand any country row by default', () => {
      setup([])
      // region labels only appear when country row is expanded
      expect(screen.queryByText('Hsinchu')).not.toBeInTheDocument()
    })
  })

  describe('all-facilities toggle', () => {
    it('switches from "all" mode to explicit list when unchecked', () => {
      const { onChange } = setup([])
      const allCheckbox = screen.getByLabelText('All Facilities')
      fireEvent.click(allCheckbox)
      // When isAll=true and user clicks, the component calls onChange(allFabs)
      // — switching to "everything selected explicitly" mode.
      expect(onChange).toHaveBeenCalled()
      const calledWith = onChange.mock.calls[0][0] as string[]
      expect(calledWith).toContain('Fab14')
      expect(calledWith).toContain('Fab18')
      expect(calledWith).toContain('Fab21')
      expect(calledWith.length).toBeGreaterThan(10)
    })

    it('switches back to "all" mode (empty array) when ticked while in explicit mode', () => {
      const allFabs = [
        'Fab2', 'Fab3', 'Fab5', 'Fab6', 'Fab8', 'Fab12',
        'Fab14', 'Fab18', 'Fab15', 'Fab20', 'Fab22',
        'Fab21', 'Fab23', 'ESMC',
      ]
      const { onChange } = setup(allFabs)
      const allCheckbox = screen.getByLabelText('All Facilities')
      fireEvent.click(allCheckbox)
      expect(onChange).toHaveBeenCalledWith([])
    })
  })

  describe('country expansion', () => {
    it('expands Taiwan to show its regions when clicked', () => {
      setup(['Fab14'])  // explicit mode so children are interactable
      fireEvent.click(screen.getByText('Taiwan'))
      expect(screen.getByText('Hsinchu')).toBeInTheDocument()
      expect(screen.getByText('Miaoli / Zhunan')).toBeInTheDocument()
    })

    it('shows the fabs-count badge on each country row', () => {
      setup([])
      // Taiwan has 11 fabs (6+2+1+1+1), USA 1, Japan 1, Germany 1
      expect(screen.getByText('(11 fabs)')).toBeInTheDocument()
    })
  })

  describe('explicit fab selection', () => {
    it('adds a fab to value when its checkbox is ticked', () => {
      const { onChange } = setup(['Fab14'])
      fireEvent.click(screen.getByText('Taiwan'))
      fireEvent.click(screen.getByText('Miaoli / Zhunan'))
      const fab18Checkbox = screen.getByRole('checkbox', { name: /Fab18/i })
      fireEvent.click(fab18Checkbox)
      expect(onChange).toHaveBeenCalledWith(['Fab14', 'Fab18'])
    })

    it('removes a fab from value when its checkbox is unticked', () => {
      const { onChange } = setup(['Fab14', 'Fab18'])
      fireEvent.click(screen.getByText('Taiwan'))
      fireEvent.click(screen.getByText('Miaoli / Zhunan'))
      const fab14Checkbox = screen.getByRole('checkbox', { name: /Fab14/i })
      fireEvent.click(fab14Checkbox)
      expect(onChange).toHaveBeenCalledWith(['Fab18'])
    })
  })

  describe('disabled state when isAll=true', () => {
    it('disables individual fab checkboxes', () => {
      setup([])
      fireEvent.click(screen.getByText('Taiwan'))
      fireEvent.click(screen.getByText('Miaoli / Zhunan'))
      const fab14Checkbox = screen.getByRole('checkbox', { name: /Fab14/i }) as HTMLInputElement
      expect(fab14Checkbox.disabled).toBe(true)
      expect(fab14Checkbox.checked).toBe(true)
    })
  })
})
