import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { AlertTriangle, X } from 'lucide-react'
import type { MyReminder } from '../api/reminders'

interface Props {
  reminders: MyReminder[]
  onClose: () => void
}

export default function ReminderModal({ reminders, onClose }: Readonly<Props>) {
  const { t } = useTranslation()
  const navigate = useNavigate()

  if (reminders.length === 0) return null

  const first = reminders[0]
  const body =
    reminders.length === 1
      ? t('reminder.modalBody', { event: first.event_title })
      : t('reminder.modalBodyMulti', { count: reminders.length })

  const goReport = () => {
    onClose()
    navigate(`/events/${first.event_id}/report`)
  }

  const handleOverlayClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (e.target === e.currentTarget) {
      onClose()
    }
  }

  const handleOverlayKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (e.key === 'Escape' || e.key === 'Enter' || e.key === ' ') {
      onClose()
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      role="button"
      tabIndex={0}
      aria-label="Close modal overlay"
      onClick={handleOverlayClick}
      onKeyDown={handleOverlayKeyDown}
    >
      <div
        className="relative w-full max-w-md mx-4 bg-white rounded-2xl shadow-2xl border-t-8 border-red-600 animate-[fadeIn_0.2s_ease-out]"
      >
        <style>{`
          @keyframes fadeIn {
            from { opacity: 0; transform: scale(0.95) translateY(-10px); }
            to   { opacity: 1; transform: scale(1) translateY(0); }
          }
        `}</style>
        <button
          onClick={onClose}
          className="absolute top-3 right-3 text-gray-400 hover:text-gray-700 transition"
          aria-label="close"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-12 h-12 rounded-full bg-red-100 flex items-center justify-center">
              <AlertTriangle className="w-7 h-7 text-red-600 animate-pulse" />
            </div>
            <h2 className="text-xl font-bold text-gray-900">{t('reminder.modalTitle')}</h2>
          </div>

          <p className="text-gray-700 leading-relaxed mb-2">{body}</p>

          {reminders.length > 1 && (
            <ul className="mt-3 mb-4 max-h-40 overflow-y-auto text-sm text-gray-600 space-y-1">
              {reminders.map((r) => (
                <li key={r.event_id} className="flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-red-500 shrink-0" />
                  <span className="truncate">{r.event_title}</span>
                </li>
              ))}
            </ul>
          )}

          <div className="mt-6 flex items-center gap-3">
            <button
              onClick={goReport}
              className="flex-1 py-2.5 bg-red-600 hover:bg-red-700 text-white rounded-lg font-medium transition"
            >
              {t('reminder.modalGoReport')}
            </button>
            <button
              onClick={onClose}
              className="px-4 py-2.5 text-gray-600 hover:bg-gray-100 rounded-lg font-medium transition"
            >
              {t('reminder.modalLater')}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
