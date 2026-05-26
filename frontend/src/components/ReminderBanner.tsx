import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { AlertTriangle } from 'lucide-react'
import { getMyReminders, type MyReminder } from '../api/reminders'
import { useAuth } from '../contexts/AuthContext'

const POLL_INTERVAL_MS = 20_000

export default function ReminderBanner() {
  const { user } = useAuth()
  const { t } = useTranslation()
  const [reminders, setReminders] = useState<MyReminder[]>([])
  const timerRef = useRef<number | undefined>(undefined)

  useEffect(() => {
    if (!user || user.role !== 'employee') {
      setReminders([])
      return
    }

    let cancelled = false
    const fetchOnce = async () => {
      try {
        const data = await getMyReminders()
        if (!cancelled) setReminders(data)
      } catch {
        // Silent — banner just won't show on transient failure.
      }
    }

    fetchOnce()
    timerRef.current = window.setInterval(fetchOnce, POLL_INTERVAL_MS)
    return () => {
      cancelled = true
      if (timerRef.current) window.clearInterval(timerRef.current)
    }
  }, [user])

  if (!user || user.role !== 'employee' || reminders.length === 0) return null

  const message =
    reminders.length === 1
      ? t('reminder.banner', { event: reminders[0].event_title })
      : t('reminder.bannerMulti', { count: reminders.length })

  const text = `${message}    •    ${message}    •    ${message}`

  return (
    <div className="relative overflow-hidden bg-red-600 border-y-2 border-red-800 shadow-md">
      <style>{`
        @keyframes safety-marquee {
          0% { transform: translateX(0%); }
          100% { transform: translateX(-50%); }
        }
        .safety-marquee-track {
          display: inline-block;
          padding-left: 100%;
          animation: safety-marquee 22s linear infinite;
          will-change: transform;
        }
      `}</style>
      <div className="flex items-center gap-3 py-3 px-4">
        <AlertTriangle className="w-7 h-7 text-yellow-200 shrink-0 animate-pulse" />
        <div className="flex-1 overflow-hidden whitespace-nowrap">
          <span className="safety-marquee-track text-2xl font-extrabold tracking-wide text-white drop-shadow">
            {text}
          </span>
        </div>
      </div>
    </div>
  )
}
