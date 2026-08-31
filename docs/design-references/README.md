# Referências de design (externas)

Capturas de tela de sites de terceiros usadas **apenas como referência
visual interna** — estudo de layout, tipografia, densidade, paleta e
padrões de UI para o frontend do Hub. Não são material de produto e não
vão para `docs/site/`.

> **Uso e atribuição.** Cada imagem é propriedade dos respectivos donos.
> Ficam aqui a título de _fair use_ para pesquisa de design interna. Não
> republicar, não usar em material externo, não versionar credencial ou
> conteúdo logado. Toda captura carrega URL de origem e data no
> `manifest.json`.

## Estrutura

```
docs/design-references/
├── README.md            # este arquivo
├── sources.json         # lista declarativa: sites → páginas a capturar
├── manifest.json        # gerado: metadados de cada captura (URL, data, viewport, arquivos)
└── captures/
    ├── thebrandtechgroup/   # site single-page: home + âncoras de seção + páginas soltas
    │   ├── home--desktop.png            # viewport 1440×900 (PNG — nitidez de UI)
    │   ├── home--desktop.fullpage.jpg   # página inteira (JPEG q82, teto de 12000 px)
    │   └── section-leadership--desktop.png   # âncora de seção (viewportOnly)
    └── jellyfish/           # 15 páginas estruturais, só locale en-us
```

Sites cobertos: **The Brandtech Group** e **Jellyfish**. DP6 foi deixado
de fora a pedido.

Convenção de nome: `<slug>--desktop.png` (viewport) e
`<slug>--desktop.fullpage.jpg` (página inteira, omitida quando
`viewportOnly`). `slug` vem de `sources.json`. Um site = uma pasta.
Viewport padrão 1440×900, `deviceScaleFactor: 2` (imagens em 2×).
Full-page tem teto de 12000 px CSS (listagens de scroll infinito).

## Regenerar / adicionar telas

As imagens são **geradas, não editadas à mão**. Para adicionar uma tela,
acrescente um objeto em `pages` do site correspondente em `sources.json`
e rode a captura.

### Opção A — Playwright MCP (mecanismo primário)

Servidor `playwright` já registrado no escopo local
(`claude mcp add playwright --scope local -- npx -y @playwright/mcp@latest`).
Reinicie a sessão do Claude Code para as ferramentas de browser
aparecerem; então peça a captura das URLs de `sources.json` para
`captures/<site>/`.

### Opção B — script (fallback reproduzível)

```bash
npm i playwright                                        # o repo não declara essa dependência (uso pontual)
node scripts/capture-design-refs.mjs                    # todos os sites
node scripts/capture-design-refs.mjs --site jellyfish   # um site
node scripts/capture-design-refs.mjs --headed           # ver o browser
```

O script lê `sources.json`, tira viewport + full-page de cada página,
grava em `captures/<site>/` e reescreve `manifest.json`.

### Pré-requisito de sistema (uma vez)

O Chromium do Playwright precisa de bibliotecas do SO que não vêm por
padrão nesta imagem WSL (`libnss3`, `libnspr4`, `libasound2`). Instale
uma vez, com privilégio de root:

```bash
sudo npx --yes playwright install-deps chromium
# ou, direto:
sudo apt-get update && sudo apt-get install -y libnss3 libnspr4 libasound2t64
```

Sem isso, tanto a Opção A quanto a B falham no launch do browser
(`error while loading shared libraries: libnspr4.so`).
