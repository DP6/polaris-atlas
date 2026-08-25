import { Badge } from '@/components/ui/badge'
import { formatRelativeToNow } from '@/lib/format'

interface CacheStalenessBadgeProps {
  cacheUpdatedAt: string | null
}

// null = a resposta veio ao vivo nesta chamada (cache miss) — não exibe
// nada, já que não há staleness a comunicar. Usado por lineage, órfãs e
// mapa de acesso, as três telas cujo backend passou a ler de um cache
// pré-computado (job diário D-1, ver docs/specs/lineage.md).
export function CacheStalenessBadge({ cacheUpdatedAt }: CacheStalenessBadgeProps) {
  if (!cacheUpdatedAt) return null

  return (
    <Badge variant="outline" className="font-normal text-muted-foreground">
      Cache atualizado {formatRelativeToNow(cacheUpdatedAt)}
    </Badge>
  )
}
