import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  Tooltip as RechartsTooltip,
  ReferenceLine,
  ResponsiveContainer,
  XAxis,
  YAxis,
} from 'recharts'

interface BarSeries {
  key: string
  name: string
  color: string
}

interface LineSeries extends BarSeries {
  dashed?: boolean
}

interface ComboChartProps {
  data: Record<string, unknown>[]
  xKey: string
  // Coluna (uma só) — eixo Y da esquerda.
  bar: BarSeries
  // Linha(s) — eixo Y da direita (escala independente da coluna).
  lines: LineSeries[]
  // Linha de referência horizontal (ex: budget) no eixo da direita.
  refLine?: { y: number; label: string; color?: string }
  height?: number
  valueFormat?: (value: number) => string
}

// Coluna + linha(s) num container `bloco` — extraído do `<ComposedChart>`
// de BudgetPage. Eixo Y duplo (coluna à esquerda, linha à direita) porque
// as escalas costumam ser bem diferentes (diário × acumulado). Usado por
// BudgetPage, FinOps overview e Admin "Acessos ao Hub".
export function ComboChart({
  data,
  xKey,
  bar,
  lines,
  refLine,
  height = 224,
  valueFormat,
}: ComboChartProps) {
  const fmt = valueFormat ?? ((value: number) => String(value))

  return (
    <div className="w-full shrink-0 rounded-lg border border-border bg-card p-4" style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data}>
          <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
          <XAxis dataKey={xKey} tick={{ fontSize: 11 }} />
          <YAxis
            yAxisId="bar"
            tick={{ fontSize: 11 }}
            width={48}
            tickFormatter={(v) => fmt(Number(v))}
          />
          <YAxis
            yAxisId="line"
            orientation="right"
            tick={{ fontSize: 11 }}
            width={48}
            tickFormatter={(v) => fmt(Number(v))}
          />
          <RechartsTooltip formatter={(value) => fmt(Number(value))} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Bar yAxisId="bar" dataKey={bar.key} name={bar.name} fill={bar.color} barSize={16} />
          {lines.map((ln) => (
            <Line
              key={ln.key}
              yAxisId="line"
              type="monotone"
              dataKey={ln.key}
              name={ln.name}
              stroke={ln.color}
              strokeWidth={2}
              strokeDasharray={ln.dashed ? '4 4' : undefined}
              dot={ln.dashed ? false : { r: 3 }}
            />
          ))}
          {refLine && (
            <ReferenceLine
              yAxisId="line"
              y={refLine.y}
              stroke={refLine.color ?? 'var(--color-status-error)'}
              strokeDasharray="5 5"
              label={{ value: refLine.label, position: 'insideTopRight', fontSize: 10 }}
            />
          )}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}
