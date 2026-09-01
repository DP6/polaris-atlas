import type { SLAStatus } from '@/types/freshness'

export const SLA_LABELS: Record<SLAStatus, string> = {
  ok: 'Até 12h',
  warning_12_24: '12h a 24h',
  warning_24_48: '24h a 48h',
  warning_48_7d: '48h a 7d',
  warning_7d_1m: '7d a 1m',
  stale: '>1 mês',
}

// Cor de TEXTO/ÍCONE por faixa — variantes -foreground, contraste AA nos
// dois temas (ver docs/frontend/accessibility.md). Usar em número/texto.
export const SLA_TEXT_COLOR: Record<SLAStatus, string> = {
  ok: 'text-status-ok-foreground',
  warning_12_24: 'text-status-ok-foreground',
  warning_24_48: 'text-status-warn-foreground',
  warning_48_7d: 'text-status-warn-foreground',
  warning_7d_1m: 'text-status-error-foreground',
  stale: 'text-status-error-foreground',
}

// Cor de PREENCHIMENTO por faixa — valor cru --status-* (basta 3:1).
// Usar em bolinha/dot/barra, nunca em texto.
export const SLA_FILL_COLOR: Record<SLAStatus, string> = {
  ok: 'bg-status-ok',
  warning_12_24: 'bg-status-ok',
  warning_24_48: 'bg-status-warn',
  warning_48_7d: 'bg-status-warn',
  warning_7d_1m: 'bg-status-error',
  stale: 'bg-status-error',
}

// Severidade da faixa → status do <StatusBadge> (ícone + rótulo, para
// não comunicar estado só por cor — WCAG 1.4.1).
export const SLA_SEVERITY: Record<SLAStatus, 'ok' | 'warn' | 'error'> = {
  ok: 'ok',
  warning_12_24: 'ok',
  warning_24_48: 'warn',
  warning_48_7d: 'warn',
  warning_7d_1m: 'error',
  stale: 'error',
}

export const SLA_SHORT_LABELS: Record<SLAStatus, string> = {
  ok: '≤12h',
  warning_12_24: '12-24h',
  warning_24_48: '24-48h',
  warning_48_7d: '48h-7d',
  warning_7d_1m: '7d-1m',
  stale: '>1m',
}

export const SLA_ORDER: SLAStatus[] = [
  'ok',
  'warning_12_24',
  'warning_24_48',
  'warning_48_7d',
  'warning_7d_1m',
  'stale',
]
