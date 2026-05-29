import { useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { ChevronDown, ChevronRight } from 'lucide-react'

const FACILITIES = [
  {
    key: 'taiwan',
    regions: [
      { key: 'hsinchu', fabs: ['Fab2', 'Fab3', 'Fab5', 'Fab6', 'Fab8', 'Fab12'] },
      { key: 'zhunan', fabs: ['Fab14', 'Fab18'] },
      { key: 'taichung', fabs: ['Fab15'] },
      { key: 'tainan', fabs: ['Fab20'] },
      { key: 'kaohsiung', fabs: ['Fab22'] },
    ],
  },
  {
    key: 'usa',
    regions: [{ key: 'arizona', fabs: ['Fab21'] }],
  },
  {
    key: 'japan',
    regions: [{ key: 'kumamoto', fabs: ['Fab23'] }],
  },
  {
    key: 'germany',
    regions: [{ key: 'dresden', fabs: ['ESMC'] }],
  },
]

interface Props {
  value: string[]
  onChange: (fabs: string[]) => void
}

interface FabCheckboxProps {
  fab: string
  checked: boolean
  disabled: boolean
  onChange: (fab: string) => void
}

function FabCheckbox({ fab, checked, disabled, onChange }: Readonly<FabCheckboxProps>) {
  return (
    <label
      className={`flex items-center gap-2 px-3 py-1 rounded ${
        disabled ? 'cursor-not-allowed opacity-70' : 'hover:bg-gray-50 cursor-pointer'
      }`}
    >
      <input
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={() => onChange(fab)}
        className="w-4 h-4 accent-blue-900 shrink-0 disabled:cursor-not-allowed"
      />
      <span className="font-mono">{fab}</span>
    </label>
  )
}

function Checkbox({
  checked,
  indeterminate = false,
  disabled = false,
  onChange,
  onClick,
}: Readonly<{
  checked: boolean
  indeterminate?: boolean
  disabled?: boolean
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void
  onClick?: (e: React.MouseEvent<HTMLInputElement>) => void
}>) {
  const ref = useRef<HTMLInputElement>(null)
  if (ref.current) ref.current.indeterminate = indeterminate
  return (
    <input
      ref={ref}
      type="checkbox"
      checked={checked}
      disabled={disabled}
      onChange={onChange}
      onClick={onClick}
      className="w-4 h-4 accent-blue-900 shrink-0 disabled:cursor-not-allowed"
    />
  )
}

export default function FacilitySelector({ value, onChange }: Readonly<Props>) {
  const { t } = useTranslation()
  const [expanded, setExpanded] = useState<Record<string, boolean>>({})

  const isAll = value.length === 0
  const allFabs = FACILITIES.flatMap(c => c.regions.flatMap(r => r.fabs))

  const toggle = (key: string) =>
    setExpanded(p => ({ ...p, [key]: !p[key] }))

  const toggleGroup = (fabs: string[]) => {
    const allSelected = fabs.every(f => value.includes(f))
    onChange(
      allSelected
        ? value.filter(f => !fabs.includes(f))
        : [...value, ...fabs.filter(f => !value.includes(f))],
    )
  }

  const toggleFab = (fab: string) =>
    onChange(value.includes(fab) ? value.filter(f => f !== fab) : [...value, fab])

  return (
    <div className="border rounded-lg overflow-hidden text-sm">
      {/* 全廠區 */}
      <label className="flex items-center gap-2 px-3 py-2.5 bg-gray-50 border-b cursor-pointer hover:bg-gray-100 select-none">
        <input
          type="checkbox"
          checked={isAll}
          onChange={() => isAll ? onChange(allFabs) : onChange([])}
          className="w-4 h-4 accent-blue-900 cursor-pointer shrink-0"
        />
        <span className="font-semibold">{t('event.allFacilities')}</span>
      </label>

      {FACILITIES.map(country => {
        const countryFabs = country.regions.flatMap(r => r.fabs)
        const allCountry = isAll || countryFabs.every(f => value.includes(f))
        const someCountry = !isAll && countryFabs.some(f => value.includes(f))
        const countryOpen = expanded[country.key]

        return (
          <div key={country.key} className="border-b last:border-0">
            {/* Country row */}
            <button
              type="button"
              className="w-full flex items-center gap-2 px-3 py-2 bg-white hover:bg-gray-50 cursor-pointer select-none text-left focus:outline-none"
              onClick={() => toggle(country.key)}
            >
              {countryOpen
                ? <ChevronDown className="w-4 h-4 text-gray-400 shrink-0" />
                : <ChevronRight className="w-4 h-4 text-gray-400 shrink-0" />}
              <Checkbox
                checked={allCountry}
                indeterminate={someCountry && !allCountry}
                disabled={isAll}
                onChange={e => { e.stopPropagation(); toggleGroup(countryFabs) }}
                onClick={e => e.stopPropagation()}
              />
              <span className="font-semibold">{t(`facility.${country.key}`)}</span>
              <span className="text-xs text-gray-400 ml-1.5">
                {t('facility.fabsCount', { count: countryFabs.length })}
              </span>
            </button>

            {countryOpen && country.regions.map(region => {
              const allRegion = isAll || region.fabs.every(f => value.includes(f))
              const someRegion = !isAll && region.fabs.some(f => value.includes(f))
              const regionKey = `${country.key}-${region.key}`
              const regionOpen = expanded[regionKey]

              return (
                <div key={region.key} className="ml-7 border-t border-gray-100">
                  {/* Region row */}
                  <button
                    type="button"
                    className="w-full flex items-center gap-2 px-3 py-1.5 bg-gray-50/70 hover:bg-gray-100 cursor-pointer select-none text-left focus:outline-none"
                    onClick={() => toggle(regionKey)}
                  >
                    {regionOpen
                      ? <ChevronDown className="w-3 h-3 text-gray-400 shrink-0" />
                      : <ChevronRight className="w-3 h-3 text-gray-400 shrink-0" />}
                    <Checkbox
                      checked={allRegion}
                      indeterminate={someRegion && !allRegion}
                      disabled={isAll}
                      onChange={e => { e.stopPropagation(); toggleGroup(region.fabs) }}
                      onClick={e => e.stopPropagation()}
                    />
                    <span className="text-gray-700">{t(`facility.${region.key}`)}</span>
                    <span className="text-xs text-gray-400 ml-1.5">{region.fabs.join(', ')}</span>
                  </button>

                  {/* Individual fabs */}
                  {regionOpen && (
                    <div className="ml-6 py-1 border-t border-gray-100">
                      {region.fabs.map(fab => (
                        <FabCheckbox
                          key={fab}
                          fab={fab}
                          checked={isAll || value.includes(fab)}
                          disabled={isAll}
                          onChange={toggleFab}
                        />
                      ))}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )
      })}
    </div>
  )
}
