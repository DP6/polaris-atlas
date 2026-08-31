export function formatBytes(bytes: number | null): string {
  if (bytes === null) return '—'
  if (bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let value = bytes
  let unitIndex = 0
  while (value >= 1000 && unitIndex < units.length - 1) {
    value /= 1000
    unitIndex += 1
  }
  return `${value.toFixed(2)} ${units[unitIndex]}`
}

export function formatNumber(value: number | null): string {
  if (value === null) return '—'
  return new Intl.NumberFormat('pt-BR').format(value)
}

export function formatDate(iso: string | null): string {
  if (!iso) return '—'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return '—'
  return new Intl.DateTimeFormat('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

export function formatPercent(value: number | null, digits = 1): string {
  if (value === null) return '—'
  return `${value.toFixed(digits)}%`
}

// Custo em dólar — 6 casas pra valores subcentavo (storage de tabela órfã
// costuma ser US$ 0.00xxxx/mês), 2 casas no resto. Usado por FinOps,
// órfãs e o scanner de desperdício de Storage.
export function formatUsd(value: number): string {
  return `US$ ${value.toFixed(value < 0.01 ? 6 : 2)}`
}

// Usado pelo indicador de staleness do cache de audit log de
// lineage/acesso/órfãs (cache_updated_at) — o ciclo de refresh é diário
// (D-1), então o texto normalmente cai em horas/dias, não minutos, mas
// um gatilho manual de admin pode deixar o cache "recém-atualizado".
export function formatRelativeToNow(iso: string | null): string {
  if (!iso) return '—'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return '—'

  const diffMs = Date.now() - date.getTime()
  const diffMinutes = Math.round(diffMs / 60_000)
  if (diffMinutes < 1) return 'agora mesmo'
  if (diffMinutes < 60) return `há ${diffMinutes} min`

  const diffHours = Math.round(diffMinutes / 60)
  if (diffHours < 24) return `há ${diffHours}h`

  const diffDays = Math.round(diffHours / 24)
  return `há ${diffDays} ${diffDays === 1 ? 'dia' : 'dias'}`
}
