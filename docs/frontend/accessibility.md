# Acessibilidade — WCAG 2.1 AA (obrigatório)

O tema claro **é usado em produção** e precisa passar AA igual ao escuro.
Esta baseline saiu da auditoria de UI/acessibilidade de 2026-08
(branch `fix/ui-a11y-tokens`, 6 fases, PR #49). Não regredir.

## Checklist (toda tela / componente)

### Contraste
- [ ] Texto normal **≥ 4.5:1**; ícone, borda e elemento de gráfico **≥ 3:1** — **nos dois temas**.
- [ ] Cor de estado como texto/ícone = classe `text-status-*-foreground` (calibrada por tema). Nunca `text-status-*` sem sufixo como texto, nunca `text-primary` como texto sobre `--background`/`--card`.
- [ ] `--muted-foreground` (o token de texto secundário) já passa ≥4.5:1 contra `--background` e `--card` — não trocar por um cinza mais claro.

### Foco de teclado
- [ ] Todo interativo tem foco visível. A regra global em `apps/frontend/src/index.css` (`:focus-visible { outline: 2px solid var(--color-ring); outline-offset: 2px }`) cobre `a[href]`, `button`, `input`, `select`, `textarea`, `summary` e os papéis ARIA (`button`, `tab`, `menuitem`, `option`, `combobox`) + `[tabindex]`.
- [ ] Não usar `outline-none` sem repor um indicador equivalente. Se um primitivo shadcn zera o outline via `@layer utilities`, a regra global (fora de `@layer`) vence — não desligar isso.
- [ ] Ordem de tab segue a ordem visual; foco não fica preso; dialog devolve o foco ao gatilho ao fechar.

### Não depender de cor
- [ ] Todo estado/erro/resultado = **ícone + texto** (`StatusBadge`, `WarningCallout`, `ApiErrorNotice`, input inválido com ícone + `role="alert"`). Nunca só um ponto/texto colorido.

### Semântica
- [ ] Um `<h1>` por rota (via `PageHeader`); seções em `<h2>`/`<h3>` reais (`SectionHeading`, `CollapsibleSection`) — sem pular nível, sem `<div>` estilizado como título.
- [ ] Toda `<label>` associada ao controle (componente `<Label htmlFor>`; `DateField` já faz).
- [ ] Filtro/combobox/toggle sem rótulo visível tem `aria-label` (ex.: `ChoiceToggle` exige `aria-label`; `role="group"` no grupo de pills).
- [ ] Regiões dinâmicas anunciam: `role="status"` (carregando, aviso), `role="alert"` (erro).

### Alvo de toque
- [ ] Botão pequeno (estrela de favoritar, ícone de ação) com área **≥ 24×24 px** (`size-6` mínimo) — WCAG 2.5.8.

### Movimento
- [ ] Nenhuma animação/transição ignora `prefers-reduced-motion` (o reset global em `index.css` já cobre; não adicionar `!important` que fure isso).

### Ícones
- [ ] Ícone decorativo: `aria-hidden="true"`. Ícone que carrega informação: rótulo textual ao lado ou `<span class="sr-only">`.

## Como verificar

1. **Contraste:** conferir cada par texto/fundo novo com uma ferramenta
   (DevTools "Contrast ratio" no color picker, ou WebAIM Contrast Checker)
   **nos dois temas** — alternar pelo `ThemeToggle`. Os valores dos
   tokens de status já vêm com o contraste anotado nos comentários do
   `index.css`.
2. **Só teclado:** navegar a tela inteira com Tab / Shift+Tab / Enter /
   Esc / setas, sem mouse. Todo alvo alcançável, foco sempre visível,
   dialog abre e fecha devolvendo o foco.
3. **Reduced motion:** ligar "reduzir movimento" no SO (ou emular em
   DevTools → Rendering → `prefers-reduced-motion`) e confirmar que
   spinners param num frame e popovers não deslizam.
4. **Estrutura:** no leitor de tela (ou extensão de acessibilidade),
   checar que há um `<h1>`, que os cabeçalhos formam uma árvore coerente,
   e que os landmarks (`<main>`, navegação) existem.
5. `pnpm lint` — o biome tem regras de acessibilidade ligadas (preset
   `recommended`); um `// biome-ignore lint/a11y/...` novo precisa de
   justificativa no comentário.
