import { useTranslation } from 'react-i18next'

interface Props {
  status: 'safe' | 'need_help' | null
  size?: 'sm' | 'md'
}

export default function StatusBadge({ status, size = 'sm' }: Props) {
  const { t } = useTranslation()

  const config = {
    safe: { bg: 'bg-green-100 text-green-800 border-green-300', label: t('status.safe') },
    need_help: { bg: 'bg-red-100 text-red-800 border-red-300', label: t('status.need_help') },
    null: { bg: 'bg-gray-100 text-gray-600 border-gray-300', label: t('status.unreported') },
  }

  const c = config[status ?? 'null']
  const sizeClass = size === 'md' ? 'px-3 py-1.5 text-sm' : 'px-2 py-0.5 text-xs'

  return (
    <span className={`inline-flex items-center rounded-full border font-medium ${c.bg} ${sizeClass}`}>
      {c.label}
    </span>
  )
}
