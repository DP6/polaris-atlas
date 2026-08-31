import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

// Estilo de link de navegação (dentro de tabela, breadcrumb, etc.).
// Cor `info` na variante -foreground: contraste AA nos dois temas (o
// amarelo --primary como texto falha AA no tema claro — ver
// docs/frontend/ui-ux-rules.md). Sublinhado no hover como afordância
// que não depende de cor.
export const linkClass = 'text-status-info-foreground hover:underline'
