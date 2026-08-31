import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

// Estilo de link de navegação (dentro de tabela, breadcrumb, etc.):
// amarelo dp6 no hover + sublinhado como afordância que não depende só
// de cor. Nota: --primary como texto tem contraste baixo no tema claro
// (~1.7:1); o hover é transiente e o sublinhado ajuda, mas não passa
// WCAG AA 1.4.3.
export const linkClass = 'hover:text-primary hover:underline'
