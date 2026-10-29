import { useMemo, useState } from 'react'
import Chart from '../components/Chart'
import FilterBar from '../components/FilterBar'
import { Bar, Empty, IssueLink, Lead, Loading, PageHeader, Section, Tag, Toggle } from '../components/ui'
import { useApi } from '../lib/api'
import { describeSlice, useFilters } from '../lib/filters'
import { fmtInt, fmtNum, fmtPct } from '../lib/format'
import { FEATURE_ORDER, featureColor, ink, issueColor } from '../lib/palette'

export default function Features() {
  const { filters } = useFilters()
  const [general, setGeneral] = useState(false)
  const q = useApi('/features/matrix', { ...filters, include_general: general })
  const cells: any[] = q.data?.data ?? []
  const feats: any[] = q.data?.meta.features ?? []
  const total = q.data?.meta.total_mentions ?? 0
  const t = ink()

  const worst = useMemo(() => [...cells].filter((c) => c.mention_count >= 30).sort((a, b) => b.negative_ratio_pct - a.negative_ratio_pct)[0], [cells])
  const loudest = useMemo(() => [...cells].sort((a, b) => b.complaint_load - a.complaint_load)[0], [cells])

  const scatter = useMemo(() => {
    const data = cells.map((c) => ({
      value: [c.mention_count, c.negative_ratio_pct, c.avg_engagement],
      name: c.issue_category,
      itemStyle: { color: issueColor(c.issue_category) },
      label: { show: true, position: 'right', formatter: c.issue_category, color: t.ink2, fontSize: 11, fontFamily: t.sans },
    }))
    const maxEng = Math.max(...cells.map((c) => c.avg_engagement), 1)
    return {
      grid: { top: 24, bottom: 28, right: 160 },
      tooltip: { trigger: 'item', formatter: (p: any) => `<b>${p.name}</b><br/>${fmtInt(p.value[0])} mentions · ${fmtPct(p.value[1], 0)} negative · engagement ${fmtNum(p.value[2], 1)}` },
      xAxis: { type: 'value', name: 'mentions', nameLocation: 'middle', nameGap: 22, nameTextStyle: { color: t.ink3, fontSize: 11 }, splitLine: { lineStyle: { color: t.line } }, axisLabel: { color: t.ink3, fontFamily: t.mono, fontSize: 11 } },
      yAxis: { type: 'value', name: 'negative share %', nameTextStyle: { color: t.ink3, fontSize: 11, align: 'left' }, min: 0, max: 100 },
      series: [{ type: 'scatter', data, symbolSize: (v: number[]) => 8 + (v[2] / maxEng) * 22, itemStyle: { borderColor: t.surface, borderWidth: 2 }, labelLayout: { hideOverlap: true, moveOverlap: 'shiftY' } }],
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cells])

  const maxMention = Math.max(...cells.map((c) => c.mention_count), 1)

  return (
    <>
      <FilterBar supports={['date_from', 'date_to', 'model', 'ios', 'feature', 'issue']} />
      <PageHeader
        eyebrow="BR05 · Feature-level feedback analysis"
        title="Which parts of the phone get the heat?"
        lead={`Mentions, sentiment and reach per feature area and defect type for ${describeSlice(filters)}. Bubble size is average engagement, so a small-but-loud defect stands out.`}
        aside={<Toggle on={general} onChange={setGeneral} label="Include general discussion" />}
      />

      <Loading q={q} h={60}>
        {() =>
          feats.length ? (
            <Lead>
              <b>{feats[0].feature_category}</b> draws the most attention with <b className="num">{fmtInt(feats[0].mention_count)}</b> mentions
              {worst && (
                <>
                  , but the most negative conversation is about <b>{worst.issue_category}</b> (<span className="num">{fmtPct(worst.negative_ratio_pct, 0)}</span> negative)
                </>
              )}
              {loudest && loudest.issue_category !== worst?.issue_category && (
                <>
                  {' '}
                  and the one that travels furthest is <b>{loudest.issue_category}</b>
                </>
              )}
              .
            </Lead>
          ) : (
            <Empty />
          )
        }
      </Loading>

      <Section title="By feature area" sub="Mentions and negative share. The bar is relative to the largest feature." evidence={{ br: 'BR05', mart: q.data?.meta.source, endpoint: '/features/matrix', ms: q.data?._ms, dbMs: q.data?.meta.db_ms, rows: cells.length }}>
        <Loading q={q} h={200}>
          {() => (
            <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-x-10 gap-y-4">
              {feats.map((f) => (
                <div key={f.feature_category} className="flex items-center gap-4">
                  <i className="swatch" style={{ background: featureColor(f.feature_category) }} />
                  <div className="flex-1 min-w-0">
                    <div className="flex justify-between text-[13px]">
                      <span className="font-medium truncate">{f.feature_category}</span>
                      <span className="num text-ink-2">{fmtInt(f.mention_count)}</span>
                    </div>
                    <Bar pct={(f.mention_count / Math.max(...feats.map((x: any) => x.mention_count), 1)) * 100} color={featureColor(f.feature_category)} />
                    <div className="flex justify-between text-[11px] text-ink-3 num mt-0.5">
                      <span>{fmtPct((f.mention_count / total) * 100, 1)} of mentions</span>
                      <span>{fmtPct(f.negative_ratio_pct, 0)} negative</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Loading>
      </Section>

      <div className="grid lg:grid-cols-[1.1fr_1fr] gap-x-10">
        <Section title="Volume vs. negativity" sub="Top-right is the danger zone: talked about a lot and mostly negatively." evidence={{ br: 'BR05', endpoint: '/features/matrix' }}>
          <Loading q={q} h={360}>
            {() => (cells.length ? <Chart option={scatter as any} height={380} /> : <Empty />)}
          </Loading>
        </Section>

        <Section title="Feature × defect matrix" sub="Cell shade follows negative share; number is mentions." evidence={{ br: 'BR05', endpoint: '/features/matrix' }}>
          <Loading q={q} h={360}>
            {() => (
              <table className="data">
                <thead>
                  <tr>
                    <th>Feature · defect</th>
                    <th className="text-right">Mentions</th>
                    <th className="text-right">Neg %</th>
                    <th className="text-right">Eng.</th>
                    <th className="text-right">Load</th>
                  </tr>
                </thead>
                <tbody>
                  {FEATURE_ORDER.filter((f) => cells.some((c) => c.feature_category === f)).map((f) => (
                    <FeatureRows key={f} feature={f} cells={cells.filter((c) => c.feature_category === f)} maxMention={maxMention} />
                  ))}
                </tbody>
              </table>
            )}
          </Loading>
          <div className="text-[11.5px] text-ink-3 mt-2">Load = negative mentions × average engagement; a proxy for how far a complaint travels.</div>
        </Section>
      </div>

      <div className="flex flex-wrap gap-2 text-[11.5px]">
        {FEATURE_ORDER.map((f) => (
          <Tag key={f} color={featureColor(f)}>
            {f}
          </Tag>
        ))}
      </div>
    </>
  )
}

function FeatureRows({ feature, cells, maxMention }: { feature: string; cells: any[]; maxMention: number }) {
  const sum = cells.reduce((a, c) => a + c.mention_count, 0)
  return (
    <>
      <tr className="bg-surface-2/60">
        <td className="font-medium" colSpan={1}>
          <span className="inline-flex items-center gap-2">
            <i className="swatch" style={{ background: featureColor(feature) }} />
            {feature}
          </span>
        </td>
        <td className="num text-right font-medium">{fmtInt(sum)}</td>
        <td colSpan={3}></td>
      </tr>
      {cells.map((c) => (
        <tr key={c.issue_category}>
          <td className="pl-6">
            <IssueLink issue={c.issue_category} />
          </td>
          <td className="text-right">
            <span className="inline-block min-w-[52px] px-1.5 py-0.5 rounded-sm num text-right" style={{ background: `color-mix(in oklab, var(--neg) ${Math.round(c.negative_ratio_pct * 0.8)}%, transparent)`, color: c.negative_ratio_pct > 55 ? '#fff' : 'inherit' }}>
              {fmtInt(c.mention_count)}
            </span>
            <span className="sr-only">{fmtPct((c.mention_count / maxMention) * 100, 0)} of max</span>
          </td>
          <td className="num text-right">{fmtPct(c.negative_ratio_pct, 0)}</td>
          <td className="num text-right text-ink-2">{fmtNum(c.avg_engagement, 0)}</td>
          <td className="num text-right text-ink-2">{fmtInt(c.complaint_load)}</td>
        </tr>
      ))}
    </>
  )
}
