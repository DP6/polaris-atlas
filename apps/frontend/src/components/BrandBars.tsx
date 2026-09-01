// Motivo gráfico dp6 — 3 barras diagonais (a última preenchida de amarelo)
// no canto direito de um cabeçalho. Puramente decorativo (`aria-hidden`);
// todo o estilo está em `.dp6-brand-bars` no index.css. Usado pelo
// `PageHeader` quando `showBrandBars` está ligado.
export function BrandBars() {
  return (
    <span aria-hidden="true" className="dp6-brand-bars">
      <i />
      <i />
      <i className="fill" />
    </span>
  )
}
