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

function IndeterminateCheckbox({
  checked,
  indeterminate,
  onChange,
  onClick,
}: {
  checked: boolean
  indeterminate: boolean
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void
  onClick?: (e: React.MouseEvent<HTMLInputElement>) => void
}) {
  const ref = useRef<HTMLInputElement>(null)
  if (ref.current) ref.current.indeterminate = indeterminate
  return (
    <input
      ref={ref}
      type="checkbox"
      checked={checked}
      onChange={onChange}
      onClick={onClick}
      className="w-4 h-4 accent-blue-900 cursor-pointer"
    />
  )
}

export default function FacilitySelector({ value, onChange }: Props) {
  const { t } = useTranslation()
  const [expanded, setExpanded] = useState<Record<string, boolean>>({})

  const toggle = (key: string) =>
    setExpanded(p => ({ ...p, [key]: !p[key] }))

  const toggleFab = (fab: string) =>
    onChange(value.includes(fab) ? value.filter(f => f !== fab) : [...value, fab])

  const toggleGroup = (fabs: string[]) => {
    const allSelected = fabs.every(f => value.includes(f))
    onChange(
      allSelected
        ? value.filter(f => !fabs.includes(f))
        : [...value, ...fabs.filter(f => !value.includes(f))],
    )
  }

  return (
    <div className="border rounded-lg overflow-hidden text-sm">
      {/* All Facilities option */}
      <label className="flex items-center gap-2 px-3 py-2 bg-gray-50 border-b cursor-pointer hover:bg-gray-100">
        <input
          type="checkbox"
          checked={value.length === 0}
          onChange={() => onChange([])}
          className="w-4 h-4 accent-blue-900 cursor-pointer"
        />
        <span className="font-medium">{t('event.allFacilities')}</span>
      </label>

      {FACILITIES.map(country => {
        const countryFabs = country.regions.flatMap(r => r.fabs)
        const allCountry = countryFabs.every(f => value.includes(f))
        const someCountry = countryFabs.some(f => value.includes(f))
        const countryOpen = expanded[country.key]

        return (
          <div key={country.key} className="border-b last:border-0">
            {/* Country row */}
            <div
              className="flex items-center gap-2 px-3 py-2 bg-white hover:bg-gray-50 cursor-pointer select-none"
              onClick={() => toggle(country.key)}
            >
              {countryOpen
                ? <ChevronDown className="w-4 h-4 text-gray-400 shrink-0" />
                : <ChevronRight className="w-4 h-4 text-gray-400 shrink-0" />}
              <IndeterminateCheckbox
                checked={allCountry}
                indeterminate={someCountry && !allCountry}
                onChange={e => { e.stopPropagation(); toggleGroup(countryFabs) }}
                onClick={e => e.stopPropagation()}
              />
              <span className="font-semibold">{t(`facility.${country.key}`)}</span>
              <span className="ml-auto text-xs text-gray-400">{countryFabs.join(', ')}</span>
            </div>

            {countryOpen && country.regions.map(region => {
              const allRegion = region.fabs.every(f => value.includes(f))
              const someRegion = region.fabs.some(f => value.includes(f))
              const regionKey = `${country.key}-${region.key}`
              const regionOpen = expanded[regionKey]

              return (
                <div key={region.key} className="ml-6 border-t border-gray-100">
                  {/* Region row */}
                  <div
                    className="flex items-center gap-2 px-3 py-1.5 bg-gray-50/60 hover:bg-gray-100 cursor-pointer select-none"
                    onClick={() => toggle(regionKey)}
                  >
                    {regionOpen
                      ? <ChevronDown className="w-3 h-3 text-gray-400 shrink-0" />
                      : <ChevronRight className="w-3 h-3 text-gray-400 shrink-0" />}
                    <IndeterminateCheckbox
                      checked={allRegion}
                      indeterminate={someRegion && !allRegion}
                      onChange={e => { e.stopPropagation(); toggleGroup(region.fabs) }}
                      onClick={e => e.stopPropagation()}
                    />
                    <span className="text-gray-700">{t(`facility.${region.key}`)}</span>
                    <span className="ml-auto text-xs text-gray-400">{region.fabs.join(', ')}</span>
                  </div>

                  {/* Individual fabs */}
                  {regionOpen && (
                    <div className="ml-6 py-1 space-y-0.5 border-t border-gray-100">
                      {region.fabs.map(fab => (
                        <label
                          key={fab}
                          className="flex items-center gap-2 px-3 py-1 hover:bg-gray-50 cursor-pointer rounded"
                        >
                          <input
                            type="checkbox"
                            checked={value.includes(fab)}
                            onChange={() => toggleFab(fab)}
                            className="w-4 h-4 accent-blue-900 cursor-pointer"
                          />
                          <span className="font-mono">{fab}</span>
                        </label>
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
