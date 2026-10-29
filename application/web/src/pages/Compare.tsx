import clsx from 'clsx'
import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import Chart from '../components/Chart'
import FilterBar from '../components/FilterBar'
import { Empty, Lead, Loading, PageHeader, Section, Segmented, Toggle } from '../components/ui'
import { useApi } from '../lib/api'
import { useFilters } from '../lib/filters'
import { fmtInt, fmtNum, fmtPct } from '../lib/format'
import { ink, slotColor } from '../lib/palette'

type Mode = 'models' | 'ios'

export default function Compare() {
  const { filters } = useFilters()
  const [sp, setSp] = useSearchParams()
  const mode = (sp.get('mode') as Mode) || 'models'
  const picked = useMemo(() => (sp.get('pick') ?? '').split(',').filter(Boolean), [sp])
  const [general, setGeneral] = useState(false)
  const options = useApi('/compare/options', { feature: filters.feature, include_general: general })
  const gens = useApi('/compare/generations', { feature: filters.feature, include_general: general })

  const opt = options.data?.meta
  const choices: { name: string; total_feedback: number }[] = mode === 'models' ? (opt?.models ?? []).map((m: any) => ({ name: m.iphone_model, total_feedback: m.total_feedback })) : (opt?.ios_majors ?? []).map((m: any) => ({ name: m.ios_major, total_feedback: m.total_feedback }))

  // sensible default: the three largest entities
  useEffect(() => {
    if (!picked.length && choices.length) {
      const def = [...choices].sort((a, b) => b.total_feedback - a.total_feedback).slice(0, 3).map((c) => c.name)
      setSp((p) => {
        const n = new URLSearchParams(p)
        n.set('pick', def.join(','))
        return n
      }, { replace: true })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [choices.length, mode])

  const setMode = (m: Mode) =>
    setSp((p) => {
      const n = new URLSearchParams(p)
      n.set('mode', m)
      n.delete('pick')
      return n
    })
  const toggle = (name: string) =>
    setSp((p) => {
      const n = new URLSearchParams(p)
      const cur = (n.get('pick') ?? '').split(',').filter(Boolean)
      const next = cur.includes(name) ? cur.filter((c) => c !== name) : cur.length >= 4 ? [...cur.slice(1), name] : [...cur, name]
      n.set('pick', next.join(','))
      return n
    }, { replace: true })

  const cmp = useApi(mode === 'models' ? '/compare/models' : '/compare/ios', { feature: filters.feature, include_general: general, [mode === 'models' ? 'models' : 'versions']: picked.join(',') }, { enabled: picked.length > 0 })
  const d = cmp.data?.data?.[0]
  const entities: any[] = d?.entities ?? []
  const features: string[] = d?.features ?? []
  const t = ink()

  const best = entities.length ? [...entities].filter((e) => e.total_feedback > 0).sort((a, b) => a.negative_rate_pct - b.negative_rate_pct) : []

  const grouped = (key: 'share_pct' | 'negative_rate_pct' | 'avg_sentiment', fmt: (v: number | null) => string, yName: string, max?: number) => ({
    grid: { top: 36, bottom: 60 },
    legend: { show: true, top: 0, right: 0, icon: 'rect', itemWidth: 10, itemHeight: 10, textStyle: { color: t.ink2, fontSize: 11 } },
    tooltip: { formatter: (ps: any[]) => `<b>${ps[0].axisValue}</b><br/>` + ps.map((p) => `<span style="color:${p.color}">■</span> ${p.seriesName}: ${fmt(p.value)}`).join('<br/>') },
    xAxis: { data: features, axisLabel: { interval: 0, rotate: 24, fontFamily: t.sans, fontSize: 11, color: t.ink2 } },
    yAxis: { name: yName, nameTextStyle: { color: t.ink3, fontSize: 11, align: 'left' }, max },
    series: entities.map((e, i) => ({
      name: e.name,
      type: 'bar',
      barGap: '10%',
      barCategoryGap: '35%',
      data: e.features.map((f: any) => f[key]),
      itemStyle: { color: slotColor(i), borderRadius: [2, 2, 0, 0] },
    })),
  })

  const scatter = useMemo(() => {
    const rows: any[] = gens.data?.data ?? []
    const maxEng = Math.max(...rows.map((r) => r.avg_engagement), 1)
    return {
      grid: { top: 24, bottom: 28, right: 120 },
      tooltip: { trigger: 'item', formatter: (p: any) => `<b>${p.name}</b><br/>${fmtInt(p.value[0])} mentions · ${fmtPct(p.value[1], 0)} negative · engagement ${fmtNum(p.value[2], 1)}` },
      xAxis: { type: 'log', name: 'mentions (log)', nameLocation: 'middle', nameGap: 22, nameTextStyle: { color: t.ink3, fontSize: 11 }, splitLine: { lineStyle: { color: t.line } }, axisLabel: { color: t.ink3, fontFamily: t.mono, fontSize: 11 } },
      yAxis: { type: 'value', name: 'negative share %', nameTextStyle: { color: t.ink3, fontSize: 11, align: 'left' }, min: 20, max: 70 },
      series: [
        {
          type: 'scatter',
          data: rows.map((r) => {
            const idx = picked.indexOf(r.iphone_model)
            return {
              name: r.iphone_model,
              value: [r.total_feedback, r.negative_rate_pct, r.avg_engagement],
              itemStyle: { color: idx >= 0 ? slotColor(idx) : t.line2, borderColor: t.surface, borderWidth: 2 },
              label: { show: true, position: 'right', formatter: r.iphone_model, color: idx >= 0 ? t.ink : t.ink3, fontSize: 11, fontFamily: t.sans },
            }
          }),
          symbolSize: (v: number[]) => 8 + (v[2] / maxEng) * 20,
          labelLayout: { hideOverlap: true },
        },
      ],
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [gens.data, picked])

  return (
    <>
      <FilterBar supports={['feature']} />
      <PageHeader
        eyebrow="BR08 · iPhone model / iOS version comparison"
        title={mode === 'models' ? 'Which models get the most grief?' : 'Did the release make it better?'}
        lead="Side-by-side feedback profiles. Pick up to four entities; every bar uses the same scale so a difference is a real difference."
        aside={
          <div className="flex gap-2">
            <Toggle on={general} onChange={setGeneral} label="Include general discussion" />
            <Segmented value={mode} options={[{ v: 'models', label: 'iPhone models' }, { v: 'ios', label: 'iOS majors' }]} onChange={setMode} />
          </div>
        }
      />

      <div className="flex flex-wrap gap-1.5 mb-6">
        {choices.map((c) => {
          const idx = picked.indexOf(c.name)
          return (
            <button
              key={c.name}
              type="button"
              className={clsx('btn h-7', idx >= 0 && 'is-active')}
              style={idx >= 0 ? { background: slotColor(idx), borderColor: slotColor(idx), color: '#fff' } : undefined}
              onClick={() => toggle(c.name)}
            >
              {c.name} <span className="num opacity-70">{fmtInt(c.total_feedback)}</span>
            </button>
          )
        })}
        {!choices.length && !options.isLoading && <span className="text-ink-3 text-[13px]">No entities with enough feedback.</span>}
      </div>

      {picked.length > 0 && (
        <Loading q={cmp} h={60}>
          {() =>
            best.length >= 2 ? (
              <Lead>
                <b>{best[0].name}</b> has the healthiest profile at <b className="num">{fmtPct(best[0].negative_rate_pct, 0)}</b> negative, while <b>{best[best.length - 1].name}</b> is the sorest at <b className="num">{fmtPct(best[best.length - 1].negative_rate_pct, 0)}</b>; a gap of{' '}
                <b className="num">{fmtNum(best[best.length - 1].negative_rate_pct - best[0].negative_rate_pct, 1)} points</b>.
              </Lead>
            ) : (
              <Lead>Pick at least two entities to compare.</Lead>
            )
          }
        </Loading>
      )}

      {entities.length > 0 && (
        <div className="grid gap-6 mb-8" style={{ gridTemplateColumns: `repeat(${entities.length}, minmax(0, 1fr))` }}>
          {entities.map((e, i) => (
            <div key={e.name} className="panel p-4 border-t-[3px]" style={{ borderTopColor: slotColor(i) }}>
              <div className="font-medium text-[15px] mb-2">{e.name}</div>
              <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-[12px]">
                <Stat label={general ? 'Mentions' : 'Defect mentions'} v={fmtInt(e.total_feedback)} />
                <Stat label="Negative" v={fmtPct(e.negative_rate_pct, 0)} />
                <Stat label="Mean sentiment" v={fmtNum(e.avg_sentiment, 2)} />
                <Stat label="Engagement" v={fmtNum(e.avg_engagement, 1)} />
              </div>
            </div>
          ))}
        </div>
      )}

      {entities.length > 0 && (
        <>
          <Section title="What they talk about" sub={`Share of each entity's ${general ? '' : 'defect '}mentions by feature area. Sums to 100% per entity.`} evidence={{ br: 'BR08', mart: 'gold_model_comparison', endpoint: cmp.data ? (mode === 'models' ? '/compare/models' : '/compare/ios') : '', ms: cmp.data?._ms, dbMs: cmp.data?.meta.db_ms }}>
            <Chart option={grouped('share_pct', (v) => fmtPct(v, 1), 'share of mentions %') as any} height={280} />
          </Section>
          <Section title="How negative each area is" sub="Negative share per feature area. Thin or missing bars mean too little feedback to judge." evidence={{ br: 'BR08', endpoint: mode === 'models' ? '/compare/models' : '/compare/ios' }}>
            <Chart option={grouped('negative_rate_pct', (v) => fmtPct(v, 0), 'negative %', 100) as any} height={280} />
          </Section>
        </>
      )}

      {mode === 'models' && (
        <Section title="All models at a glance" sub="Every model with ≥ 40 mentions. Selected models are coloured; bubble size is engagement." evidence={{ br: 'BR08', endpoint: '/compare/generations', ms: gens.data?._ms }}>
          <Loading q={gens} h={360}>
            {() => (gens.data!.data.length ? <Chart option={scatter as any} height={380} /> : <Empty />)}
          </Loading>
        </Section>
      )}
    </>
  )
}

function Stat({ label, v }: { label: string; v: string }) {
  return (
    <div>
      <div className="eyebrow">{label}</div>
      <div className="num text-[18px] text-ink leading-tight">{v}</div>
    </div>
  )
}
