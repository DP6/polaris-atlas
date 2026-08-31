import { FileQuestion } from 'lucide-react'
import { Link } from 'react-router-dom'
import { EmptyState } from '@/components/EmptyState'
import { buttonVariants } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export function NotFoundPage() {
  return (
    <div className="flex flex-col gap-6">
      <h1 className="font-bold text-2xl">Página não encontrada</h1>
      <EmptyState
        icon={FileQuestion}
        title="Esta rota não existe"
        description="O endereço pode estar errado ou a página foi movida."
        action={
          <Link to="/" className={cn(buttonVariants({ variant: 'outline', size: 'sm' }))}>
            Voltar ao início
          </Link>
        }
      />
    </div>
  )
}
