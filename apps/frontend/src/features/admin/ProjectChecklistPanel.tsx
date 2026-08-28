import { AlertCircle, CheckCircle2, CircleHelp, XCircle } from 'lucide-react'
import { ApiErrorNotice } from '@/components/ApiErrorNotice'
import { useProjectChecklist } from '@/features/admin/hooks'
import type { ChecklistItem, ChecklistItemName, ChecklistItemStatus } from '@/types/admin'

const ITEM_LABELS: Record<ChecklistItemName, string> = {
  bigquery: 'BigQuery',
  logging: 'Cloud Logging',
  storage: 'Cloud Storage',
  audit_logs: 'Data Access audit logs',
}

const STATUS_ICON: Record<ChecklistItemStatus, React.ReactNode> = {
  ok: <CheckCircle2 size={14} className="text-status-ok-foreground" />,
  denied: <XCircle size={14} className="text-status-error-foreground" />,
  not_found: <XCircle size={14} className="text-status-error-foreground" />,
  not_checked: <CircleHelp size={14} className="text-muted-foreground" />,
}

interface ProjectChecklistPanelProps {
  projectId: string | undefined
  // Só dispara a checagem quando true — cada verificação faz 2-3
  // leituras reais no GCP, não é pra rodar sozinha.
  enabled: boolean
}

export function ProjectChecklistPanel({ projectId, enabled }: ProjectChecklistPanelProps) {
  const checklistQuery = useProjectChecklist(projectId, { enabled })

  if (!enabled) return null
  if (checklistQuery.isLoading) {
    return <p className="text-xs text-muted-foreground">Verificando…</p>
  }
  if (checklistQuery.isError) {
    return <ApiErrorNotice error={checklistQuery.error} />
  }
  if (!checklistQuery.data) return null

  return (
    <div className="flex flex-col gap-1.5 rounded-md border border-border bg-muted/30 p-3">
      {checklistQuery.data.items.map((item: ChecklistItem) => (
        <div key={item.item} className="flex items-start gap-2 text-xs">
          <span className="mt-0.5">{STATUS_ICON[item.status]}</span>
          <div>
            <span className="font-medium">{ITEM_LABELS[item.item]}</span>
            <p className="text-muted-foreground">{item.detail}</p>
          </div>
        </div>
      ))}
      <div className="mt-1 flex items-start gap-2 text-xs text-muted-foreground">
        <AlertCircle size={14} className="mt-0.5 shrink-0" />
        <p>
          Checklist best-effort: tenta uma leitura real de cada API. Não confirma
          logging.privateLogViewer nem lê a IAM policy do projeto diretamente.
        </p>
      </div>
    </div>
  )
}
