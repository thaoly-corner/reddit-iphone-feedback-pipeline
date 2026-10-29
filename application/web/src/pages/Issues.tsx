import clsx from 'clsx'
import { useMemo, useState } from 'react'
import Chart from '../components/Chart'
import FilterBar from '../components/FilterBar'
import { Bar, Delta, Empty, Kpi, Lead, Loading, PageHeader, Section, Spark, StackBar, Tag, Toggle } from '../components/ui'
import { useApi } from '../lib/api'
import { describeSlice, useFilters } from '../lib/filters'
import { fmtDate, fmtInt, fmtNum, fmtPct } from '../lib/format'
import { featureColor, ink, issueColor, sentimentColor } from '../lib/palette'
import { usePersona } from '../lib/persona'

export default function Issues() {
  const { filters, set } = useFilters()
  const { persona } = usePersona()
  const [general, setGeneral] = useState(false)
  // ranking ignores the issue filter so the table stays complete; the selected issue drives the detail panel
  const { issue: selected, ...rest } = filters
  const ranking = useApi('/issues/ranking', { ...rest, include_general: general })
  const trends = useApi('/issues/trends', { ...rest, include_general: general })
  const detail = useApi('/issues/detail', filters, { enabled: !!selected })

  const rows: any[] = ranking.data?.data ?? []
  const top = rows[0]
  const riser = useMemo(() => [...rows].filter((r) => r.last_week_delta_pct != null && r.total_posts >= 20).sort((a, b) => b.last_week_delta_pct - a.last_week_delta_pct)[0], [rows])
  const meta = ranking.data?.meta

  return (
    <>
      <FilterBar supports={['date_from', 'date_to', 'model', 'ios', 'feature', 'issue']} />
      <PageHeader
        eyebrow="BR02 · Product issue identification  —  BR07 · Issue trend monitoring"
        title="What are people complaining about?"
        lead={`Defect categories ranked by ${persona.vocabulary.volume.toLowerCase()}, with their weekly trajectory, for ${describeSlice(rest)}. Click a row to drill into models and iOS versions.`}
        aside={<Toggle on={general} onChange={setGeneral} label="Include general discussion" />}
      />

      <Loading q={ranking} h={60}>
        {() =>
          top ? (
            <Lead>
              <b>{top.issue_category}</b> leads with <b className="num">{fmtInt(top.total_posts)}</b> reports, <b className="num">{fmtPct(top.share_of_defects_pct)}</b> of all defect reports and <b className="num">{fmtPct(top.negative_ratio_pct, 0)}</b> of them negative.
              {riser && riser.issue_category !== top.issue_category && (
                <>
                  {' '}
                  The fastest mover last week was <b>{riser.issue_category}</b>, {riser.last_week_delta_pct > 0 ? 'up' : 'down'} <b className="num">{fmtPct(Math.abs(riser.last_week_delta_pct), 0)}</b>.
                </>
              )}
            </Lead>
          ) : (
            <Empty />
          )
        }
      </Loading>

      {meta && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6 mb-8">
          <Kpi label="All feedback" value={fmtInt(meta.total_feedback)} size="md" />
          <Kpi label="Defect reports" value={fmtInt(meta.defect_feedback)} size="md" hint={<span>{fmtPct((meta.defect_feedback / meta.total_feedback) * 100, 1)} of feedback</span>} />
          <Kpi label="Issue categories" value={rows.length} size="md" />
          <Kpi label="Weeks covered" value={meta.weeks?.length ?? 0} size="md" />
        </div>
      )}

      <Section title="Issue ranking" sub="Share is relative to defect reports (general discussion excluded unless toggled). Sentiment bar: positive · neutral · negative." evidence={{ br: 'BR02', mart: 'gold_issue_summary', endpoint: '/issues/ranking', ms: ranking.data?._ms, dbMs: meta?.db_ms, rows: rows.length }}>
        <Loading q={ranking} h={300}>
          {() =>
            rows.length ? (
              <table className="data">
                <thead>
                  <tr>
                    <th className="w-8">#</th>
                    <th>Issue</th>
                    <th className="text-right">{persona.vocabulary.volume}</th>
                    <th className="w-[18%]">{persona.vocabulary.share}</th>
                    <th className="w-[14%]">Sentiment</th>
                    <th className="text-right">Eng.</th>
                    <th>Weekly</th>
                    <th className="text-right">Last wk</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => {
                    const on = r.issue_category === selected
                    return (
                      <tr key={r.issue_category} className={clsx('cursor-pointer', on && 'bg-surface-2')} onClick={() => set({ issue: on ? '' : r.issue_category, feature: '' })}>
                        <td className="num text-ink-3">{r.rank}</td>
                        <td>
                          <div className="flex items-center gap-2">
                            <i className="swatch" style={{ background: issueColor(r.issue_category) }} />
                            <span className={clsx(on && 'font-medium')}>{r.issue_category}</span>
                            <span className="text-ink-3 text-[11.5px] hidden xl:inline">{r.feature_category}</span>
                          </div>
                        </td>
                        <td className="num text-right">{fmtInt(r.total_posts)}</td>
                        <td>
                          <div className="flex items-center gap-2">
                            <Bar pct={r.share_of_defects_pct} color={issueColor(r.issue_category)} />
                            <span className="num text-[11.5px] text-ink-2 w-12 text-right">{fmtPct(r.share_of_defects_pct, 1)}</span>
                          </div>
                        </td>
                        <td>
                          <StackBar
                            parts={[
                              { v: r.positive_count, color: sentimentColor('POSITIVE'), label: 'positive' },
                              { v: r.neutral_count, color: sentimentColor('NEUTRAL'), label: 'neutral' },
                              { v: r.negative_count, color: sentimentColor('NEGATIVE'), label: 'negative' },
                            ]}
                          />
                        </td>
                        <td className="num text-right text-ink-2">{fmtNum(r.avg_engagement_score, 0)}</td>
                        <td>
                          <Spark values={r.weekly} color={issueColor(r.issue_category)} />
                        </td>
                        <td className="text-right">
                          <Delta v={r.last_week_delta_pct} invert />
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            ) : (
              <Empty />
            )
          }
        </Loading>
      </Section>

      {selected && (
        <Section title={`Drill-down · ${selected}`} sub="Daily reports and where they come from." right={<button className="btn" onClick={() => set({ issue: '' })}>Close ×</button>} evidence={{ br: 'BR02', endpoint: '/issues/detail', ms: detail.data?._ms }}>
          <Loading q={detail} h={240}>
            {() => {
              const d = detail.data!.data?.[0]
              if (!d) return <Empty />
              return <IssueDetail d={d} />
            }}
          </Loading>
        </Section>
      )}

      <Section title="Weekly trajectories" sub="BR07: weekly volume per issue (small multiples share one y-scale). Slope is a least-squares fit in reports per week." evidence={{ br: 'BR07', mart: 'gold_issue_trends', endpoint: '/issues/trends', ms: trends.data?._ms, rows: trends.data?.meta.total }}>
        <Loading q={trends} h={300}>
          {() => <TrendGrid series={trends.data!.data} weeks={trends.data!.meta.weeks} onPick={(i) => set({ issue: i, feature: '' })} />}
        </Loading>
      </Section>
    </>
  )
}

function IssueDetail({ d }: { d: any }) {
  const t = ink()
  const c = issueColor(d.issue_category)
  const daily = {
    grid: { top: 16, bottom: 8 },
    xAxis: { data: d.daily.map((r: any) => r.feedback_date), axisLabel: { formatter: (v: string) => fmtDate(v) } },
    tooltip: { formatter: (ps: any[]) => `<b>${fmtDate(ps[0].axisValue, 'EEE d MMM')}</b><br/>${ps[0].value} reports` },
    series: [{ type: 'bar', data: d.daily.map((r: any) => r.total_posts), barMaxWidth: 8, itemStyle: { color: c, borderRadius: [2, 2, 0, 0] } }],
  }
  const bars = (rows: any[], key: string) => ({
    grid: { top: 8, bottom: 8, left: 8, right: 40 },
    tooltip: { formatter: (ps: any[]) => `<b>${ps[0].name}</b><br/>${ps[0].value} reports · ${fmtPct(rows[ps[0].dataIndex].negative_ratio_pct, 0)} negative` },
    xAxis: { type: 'value', splitLine: { lineStyle: { color: t.line } } },
    yAxis: { type: 'category', inverse: true, data: rows.map((r) => r[key]), axisLabel: { color: t.ink2, fontFamily: t.sans, fontSize: 12 } },
    series: [{ type: 'bar', data: rows.map((r) => r.total_posts), barMaxWidth: 12, itemStyle: { color: c, borderRadius: [0, 2, 2, 0] }, label: { show: true, position: 'right', color: t.ink3, fontFamily: t.mono, fontSize: 11 } }],
  })
  return (
    <div className="grid lg:grid-cols-[1.3fr_1fr_1fr] gap-8">
      <div>
        <div className="flex gap-6 mb-3">
          <Kpi label="Reports" value={fmtInt(d.totals.total_posts)} size="md" bare />
          <Kpi label="Negative" value={fmtPct(d.totals.negative_ratio_pct, 0)} size="md" bare />
          <Kpi label="Avg engagement" value={fmtNum(d.totals.avg_engagement_score, 1)} size="md" bare />
        </div>
        <Chart option={daily as any} height={180} />
      </div>
      <div>
        <div className="eyebrow mb-2">By model</div>
        <Chart option={bars(d.by_model, 'iphone_model') as any} height={Math.max(160, d.by_model.length * 22 + 16)} />
      </div>
      <div>
        <div className="eyebrow mb-2">By iOS major</div>
        <Chart option={bars(d.by_ios.slice(0, 8), 'ios_major') as any} height={Math.max(160, Math.min(8, d.by_ios.length) * 22 + 16)} />
      </div>
    </div>
  )
}

function TrendGrid({ series, weeks, onPick }: { series: any[]; weeks: string[]; onPick: (issue: string) => void }) {
  const t = ink()
  const max = Math.max(...series.flatMap((s) => s.weekly_volume.map((v: number | null) => v ?? 0)), 1)
  if (!series.length) return <Empty />
  return (
    <div className="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-x-6 gap-y-2">
      {series.map((s) => {
        const c = issueColor(s.issue_category)
        const opt = {
          grid: { top: 6, bottom: 6, left: 4, right: 4, containLabel: false },
          xAxis: { data: weeks, show: false },
          yAxis: { max, show: false },
          tooltip: { formatter: (ps: any[]) => `<b>${s.issue_category}</b><br/>week of ${fmtDate(ps[0].axisValue)}: ${ps[0].value ?? 0} reports` },
          series: [{ type: 'line', data: s.weekly_volume.map((v: number | null) => v ?? 0), symbol: 'none', lineStyle: { width: 2, color: c }, areaStyle: { color: c, opacity: 0.1 } }],
        }
        return (
          <button key={s.issue_category} type="button" className="text-left group py-2 border-t border-line hover:bg-surface-2/50 rounded-sm px-1" onClick={() => onPick(s.issue_category)}>
            <div className="flex items-center justify-between gap-2 mb-1">
              <span className="text-[13px] font-medium truncate">{s.issue_category}</span>
              <Delta v={s.latest_wow_pct} invert />
            </div>
            <Chart option={opt as any} height={56} />
            <div className="flex justify-between text-[11px] text-ink-3 num mt-0.5">
              <span>{fmtInt(s.total)} total</span>
              <span style={{ color: t.ink3 }}>slope {s.slope_per_week == null ? '–' : (s.slope_per_week > 0 ? '+' : '') + fmtNum(s.slope_per_week, 2)}/wk</span>
            </div>
          </button>
        )
      })}
      <div className="col-span-full text-[11.5px] text-ink-3 mt-2 flex flex-wrap gap-x-4 gap-y-1">
        {['OS & System Software', 'Battery & Thermal', 'Camera & Optics', 'Connectivity & Network', 'Display & Touch', 'Chassis & Build Quality'].map((f) => (
          <Tag key={f} color={featureColor(f)}>
            {f}
          </Tag>
        ))}
      </div>
    </div>
  )
}
