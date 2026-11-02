import { cn, getResultColor } from '@/lib/utils'
import type { TeamFormEntry } from '@/lib/types'

interface FormBadgesProps {
  form: TeamFormEntry[] | string
  maxShow?: number
}

export function FormBadges({ form, maxShow = 5 }: FormBadgesProps) {
  // Accept either TeamFormEntry[] or a string like "WWDLW"
  const results: ('W' | 'D' | 'L')[] =
    typeof form === 'string'
      ? (form.split('').filter((c) => ['W', 'D', 'L'].includes(c)) as ('W' | 'D' | 'L')[])
      : form.map((f) => f.outcome as 'W' | 'D' | 'L')

  const display = results.slice(-maxShow)

  return (
    <div className="flex items-center gap-1" title={`Form: ${display.join('')}`}>
      {display.map((result, i) => (
        <span
          key={i}
          className={cn(
            'w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold',
            getResultColor(result)
          )}
        >
          {result}
        </span>
      ))}
    </div>
  )
}

interface FormStringBadgesProps {
  formString: string
}

export function FormStringBadges({ formString }: FormStringBadgesProps) {
  return <FormBadges form={formString} />
}
