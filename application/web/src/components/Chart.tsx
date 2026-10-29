import ReactECharts from 'echarts-for-react'
import type { EChartsOption } from 'echarts'
import { useMemo } from 'react'
import { ink } from '../lib/palette'
import { usePersona } from '../lib/persona'

interface Props {
  option: EChartsOption
  height?: number | string
  onEvents?: Record<string, (p: any) => void>
  className?: string
  group?: string
}

/** Base option: recessive hairline grid, mono tick labels, no shadows, theme-aware ink. */
export function baseOption(): EChartsOption {
  const t = ink()
  return {
    animationDuration: 350,
    animationEasing: 'cubicOut',
    textStyle: { fontFamily: t.sans, color: t.ink2 },
    color: [t.accent],
    grid: { left: 8, right: 12, top: 36, bottom: 8, containLabel: true },
    tooltip: {
      trigger: 'axis',
      backgroundColor: t.surface,
      borderColor: t.line2,
      borderWidth: 1,
      padding: [8, 10],
      textStyle: { color: t.ink, fontSize: 12, fontFamily: t.sans },
      extraCssText: 'box-shadow: 0 6px 24px rgba(0,0,0,.12); border-radius: 6px;',
      axisPointer: { type: 'line', lineStyle: { color: t.line2, type: 'dashed' } },
    },
    xAxis: {
      type: 'category',
      axisLine: { lineStyle: { color: t.line2 } },
      axisTick: { show: false },
      axisLabel: { color: t.ink3, fontFamily: t.mono, fontSize: 11, hideOverlap: true },
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: t.ink3, fontFamily: t.mono, fontSize: 11 },
      splitLine: { lineStyle: { color: t.line, width: 1 } },
      splitNumber: 4,
    },
    legend: { show: false },
  }
}

export default function Chart({ option, height = 260, onEvents, className, group }: Props) {
  const { theme } = usePersona()
  // re-create option when theme flips so CSS-var colours are re-read
  const merged = useMemo(() => {
    const base = baseOption()
    return deepMerge(base, option)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [option, theme])
  return (
    <ReactECharts
      key={theme}
      option={merged}
      notMerge
      lazyUpdate
      style={{ height, width: '100%' }}
      className={className}
      onEvents={onEvents}
      opts={{ renderer: 'svg' }}
      {...(group ? { group } : {})}
    />
  )
}

function isObj(v: any): v is Record<string, any> {
  return v && typeof v === 'object' && !Array.isArray(v)
}

function deepMerge(a: any, b: any): any {
  if (Array.isArray(b)) return b
  if (!isObj(a) || !isObj(b)) return b === undefined ? a : b
  const out: Record<string, any> = { ...a }
  for (const k of Object.keys(b)) out[k] = k in a ? deepMerge(a[k], b[k]) : b[k]
  return out
}
