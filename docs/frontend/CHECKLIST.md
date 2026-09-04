# Checklist de entrega — front-end

Fonte única. O `CLAUDE.md` (§"Contexto: Frontend") aponta para cá.

## Antes de abrir o PR

- [ ] Li `docs/frontend/README.md` e segui o roteiro de leitura do tipo
      de tarefa.
- [ ] **Tokens:** nenhum hex, `rem`/`px` de tipografia ou `rounded-[Npx]`
      solto no código — todo valor vem de um token de
      `apps/frontend/src/index.css` (documentado em
      [`design-system.md`](design-system.md)).
- [ ] Se mexi em token: `apps/frontend/src/index.css` **e**
      `docs/frontend/design-system.md` foram atualizados **no mesmo PR**.
- [ ] **Reúso:** onde havia um componente compartilhado
      (`src/components/`, ver §Catálogo) ou um padrão em
      [`patterns.md`](patterns.md), eu usei — não recriei.
- [ ] Se criei um componente compartilhado novo: adicionei linha no
      §Catálogo de `design-system.md` e apontei a tela canônica em
      [`references.md`](references.md).
- [ ] **Estados:** loading via `LoadingState`, erro via `ApiErrorNotice`,
      vazio via `EmptyState`/`EmptyStateRow`. Nada de bloco à mão.
- [ ] **Dados:** sem `fetch` direto em componente de página — só hooks de
      `features/<domínio>/hooks.ts` (TanStack Query).
- [ ] **Tipos:** TypeScript strict, sem `any` (o biome falha em
      `noExplicitAny`).
- [ ] Primitivos shadcn adicionados via CLI, não editados à mão.

## Acessibilidade (passada de [`accessibility.md`](accessibility.md))

- [ ] Contraste ≥4.5:1 texto / ≥3:1 ícone-borda **nos dois temas**
      (alternar pelo `ThemeToggle`).
- [ ] Foco de teclado visível em tudo; nenhum `outline-none` sem repor.
- [ ] Nenhum estado comunicado só por cor (ícone + texto).
- [ ] Um `<h1>` por rota (`PageHeader`); seções em `<h2>`/`<h3>` reais.
- [ ] `<label>` associada; `aria-label` em controle sem rótulo visível.
- [ ] Alvo de toque ≥ 24×24 px em botão pequeno.
- [ ] Nenhuma animação ignora `prefers-reduced-motion`.

## Verificação

- [ ] `cd apps/frontend && pnpm lint` (biome) sem erros.
- [ ] `cd apps/frontend && pnpm build` sem erros.
- [ ] Testei a tela nos dois temas e só com teclado.
- [ ] `CHANGELOG.md` atualizado se mudou arquitetura, decisão ou uma
      regra do harness.
