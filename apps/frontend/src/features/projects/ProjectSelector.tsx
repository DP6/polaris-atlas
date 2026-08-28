import { CheckCircle2, Cloud, Undo2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { ApiErrorNotice } from '@/components/ApiErrorNotice'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { RequestAccessDialog } from '@/features/admin/RequestAccessDialog'
import { useAccessibleProjects, useValidateProject } from '@/features/projects/hooks'
import { useProjectContext } from '@/features/projects/ProjectContext'
import { clearLastProjectId, getLastProjectId, setLastProjectId } from '@/hooks/useLastProject'
import { ApiError } from '@/lib/http-client'
import { cn } from '@/lib/utils'

const CUSTOM_PROJECT_OPTION = '__custom__'

export function ProjectSelector() {
  const { projectId, setProjectId } = useProjectContext()
  const [input, setInput] = useState('')
  const [submittedProjectId, setSubmittedProjectId] = useState<string | undefined>(undefined)
  const [isRestoring, setIsRestoring] = useState(false)
  const [requestAccessOpen, setRequestAccessOpen] = useState(false)
  // "access" (sem acesso no Hub a um projeto já onboardado) vs.
  // "inclusion" (projeto sem IAM concedido à SA do Hub, ou nem
  // existente) — mesmo dialog, textos e efeito de aprovação diferentes.
  const [requestType, setRequestType] = useState<'access' | 'inclusion'>('access')
  // Alterna entre o Select (lista de projetos que a SA alcança) e o campo
  // de texto livre — só um dos dois fica visível por vez, nunca os dois
  // juntos (eram redundantes antes desta versão).
  const [manualEntry, setManualEntry] = useState(false)

  const validateQuery = useValidateProject(submittedProjectId)
  // Projetos que a SA alcança (Resource Manager) — populam o Select, que
  // vira o controle principal quando não-vazio; lista vazia é normal antes
  // de qualquer projeto ganhar roles/browser (ver docs/onboarding-cliente.md)
  // e nesse caso o campo livre é o único controle mostrado.
  const accessibleProjectsQuery = useAccessibleProjects()
  const accessibleProjects = accessibleProjectsQuery.data?.projects ?? []
  // Projeto restaurado do localStorage (ou digitado antes) que não está na
  // lista da SA — mostra o campo livre com ele preenchido em vez de um
  // Select "vazio" enquanto na verdade há um project_id em validação.
  const isRestoredButUnknown = Boolean(
    submittedProjectId &&
      accessibleProjects.length > 0 &&
      !accessibleProjects.some((p) => p.project_id === submittedProjectId),
  )
  const showManualInput = accessibleProjects.length === 0 || manualEntry || isRestoredButUnknown

  // Restaura e revalida automaticamente o projeto salvo no localStorage ao
  // carregar a página (F5) — só no mount, sem o usuário precisar digitar de
  // novo.
  useEffect(() => {
    const lastProjectId = getLastProjectId()
    if (lastProjectId) {
      setInput(lastProjectId)
      setSubmittedProjectId(lastProjectId)
      setIsRestoring(true)
    }
  }, [])

  useEffect(() => {
    if (validateQuery.data?.accessible && submittedProjectId) {
      setProjectId(submittedProjectId)
      setLastProjectId(submittedProjectId)
      setIsRestoring(false)
    }
  }, [validateQuery.data, submittedProjectId, setProjectId])

  // Projeto restaurado do localStorage perdeu o acesso (ex: revogado desde
  // a última visita) — limpa o storage e volta pro campo vazio em vez de
  // deixar um project_id inválido preenchido.
  useEffect(() => {
    if (isRestoring && (validateQuery.isError || validateQuery.data?.accessible === false)) {
      clearLastProjectId()
      setInput('')
      setSubmittedProjectId(undefined)
      setIsRestoring(false)
    }
  }, [isRestoring, validateQuery.isError, validateQuery.data])

  function submitProjectId(value: string) {
    setIsRestoring(false)
    setInput(value)
    setSubmittedProjectId(value)
  }

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    if (input.trim()) submitProjectId(input.trim())
  }

  const showError = validateQuery.isError || validateQuery.data?.accessible === false
  const isNotAuthorized =
    validateQuery.error instanceof ApiError &&
    validateQuery.error.body?.error === 'project_not_authorized'
  // access_denied (SA do Hub sem IAM no GCP) e project_not_found (404)
  // ganham a mesma CTA — o usuário comum não consegue diferenciar "não
  // onboardado" de "nome errado/inexistente"; o admin investiga qual é
  // qual ao triar o pedido de inclusão.
  const isNotOnboarded =
    validateQuery.error instanceof ApiError &&
    (validateQuery.error.body?.error === 'access_denied' ||
      validateQuery.error.body?.error === 'project_not_found')

  return (
    <div className="relative">
      <form onSubmit={handleSubmit} className="flex items-center gap-2">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Cloud size={16} />
          <span>GCP Project:</span>
        </div>
        {showManualInput ? (
          <>
            <Input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="observability-hub-dev"
              className="h-7 w-56 text-sm"
            />
            <Button type="submit" size="sm" disabled={!input.trim() || validateQuery.isFetching}>
              {validateQuery.isFetching ? 'Validando…' : 'Validar'}
            </Button>
            {accessibleProjects.length > 0 && (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => setManualEntry(false)}
                aria-label="Voltar para a lista de projetos"
              >
                <Undo2 size={14} />
              </Button>
            )}
          </>
        ) : (
          <Select
            value={submittedProjectId ?? ''}
            onValueChange={(value) => {
              if (!value) return
              if (value === CUSTOM_PROJECT_OPTION) {
                setManualEntry(true)
                return
              }
              submitProjectId(value)
            }}
          >
            <SelectTrigger className="h-7 w-56 text-sm">
              <SelectValue placeholder="Selecionar projeto…" />
            </SelectTrigger>
            <SelectContent>
              {accessibleProjects.map((p) => (
                <SelectItem key={p.project_id} value={p.project_id}>
                  <span className="flex items-center gap-2">
                    {p.project_id}
                    {!p.has_access && (
                      <Badge
                        variant="outline"
                        className="border-status-warn/30 bg-status-warn/10 text-[10px] text-status-warn-foreground"
                      >
                        Sem acesso
                      </Badge>
                    )}
                  </span>
                </SelectItem>
              ))}
              <SelectItem value={CUSTOM_PROJECT_OPTION}>Outro (digitar manualmente)</SelectItem>
            </SelectContent>
          </Select>
        )}
        {validateQuery.data?.accessible && submittedProjectId === projectId && (
          <>
            <CheckCircle2
              size={16}
              className="text-status-ok-foreground"
              aria-label="Projeto acessível"
            />
            <Tooltip>
              <TooltipTrigger
                render={
                  <Badge
                    variant="outline"
                    className={cn(
                      validateQuery.data.is_native
                        ? 'border-status-ok/30 bg-status-ok/10 text-status-ok-foreground'
                        : 'border-status-warn/30 bg-status-warn/10 text-status-warn-foreground',
                    )}
                  />
                }
              >
                {validateQuery.data.is_native ? 'Projeto nativo' : 'Projeto externo'}
              </TooltipTrigger>
              <TooltipContent>
                Nativo = projeto onde o Hub está hospedado. Externo = projeto de cliente ou outro
                ambiente.
              </TooltipContent>
            </Tooltip>
          </>
        )}
      </form>

      {/* Painel flutuante em vez de um ícone com tooltip só no hover — o
          erro (principalmente "sem acesso, peça liberação") precisa ser
          visível de cara, não escondido atrás de um hover que ninguém
          tenta. Absolute pra não empurrar a altura fixa do Topbar. */}
      {showError && (
        <div className="absolute top-full left-0 z-50 mt-2 w-96">
          <ApiErrorNotice
            error={validateQuery.error}
            showFix={false}
            action={
              isNotAuthorized
                ? {
                    label: 'Solicitar acesso',
                    onClick: () => {
                      setRequestType('access')
                      setRequestAccessOpen(true)
                    },
                  }
                : isNotOnboarded
                  ? {
                      label: 'Solicitar inclusão no Hub',
                      onClick: () => {
                        setRequestType('inclusion')
                        setRequestAccessOpen(true)
                      },
                    }
                  : undefined
            }
          />
        </div>
      )}

      <RequestAccessDialog
        open={requestAccessOpen}
        onOpenChange={setRequestAccessOpen}
        initialProjectId={submittedProjectId}
        requestType={requestType}
      />
    </div>
  )
}
