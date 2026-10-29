import clsx from 'clsx'
import { useMemo, useState } from 'react'
import Chart from '../components/Chart'
import FilterBar from '../components/FilterBar'
import { Empty, Kpi, Lead, Loading, PageHeader, Section, Severity, Tag, Toggle } from '../components/ui'
import { useApi } from '../lib/api'
import { describeSlice, useFilters } from '../lib/filters'
import { fmtDate, fmtDateLong, fmtInt, fmtNum, fmtPct } from '../lib/format'
import { ink, issueColor, seq } from '../lib/palette'

export default function Emerging() {
  const { filters } = useFilters()
  const [minZ, setMinZ] = useState(2)
  const [minGrowth, setMinGrowth] = useState(150)
  const [minCurr, setMinCurr] = useState(2)
  const [excludeUnspec, setExcludeUnspec] = useState(false)
  const [pick, setPick] = useState<{ issue: string; model: string | null } | null>(null)

  const alerts = useApi('/emerging/alerts', { ...filters, min_z: minZ, min_growth: minGrowth, min_curr: minCurr, exclude_unspecified: excludeUnspec, limit: 300 })
  const heat = useApi('/emerging/heatmap', filters)
  const series = useApi('/emerging/series', { ...filters, issue: pick?.issue, model: pick?.model ?? undefined }, { enabled: !!pick })

  const rows: any[] = alerts.data?.data ?? []
  const meta = alerts.data?.meta
  const latest = rows[0]
  const topIssue = meta?.alerts_by_issue?.[0]
  const isDefault = minZ === 2 && minGrowth === 150 && minCurr === 2

  return (
    <>
      <FilterBar supports={['date_from', 'date_to', 'model', 'feature', 'issue']} />
      <PageHeader
        eyebrow="BR03 · Emerging issue detection"
        title="What is spiking right now?"
        lead={`Issues whose 3-day volume breaks away from their own 14-day baseline, per model, for ${describeSlice(filters)}. Computed upstream by the stateful sliding-window stream engine; thresholds can be adjusted here without recomputing.`}
      />

      <Loading q={alerts} h={60}>
        {() =>
          rows.length ? (
            <Lead>
              <b className="num">{fmtInt(rows.length)}</b> alerts {isDefault ? 'under the Gold rule' : 'under your thresholds'}
              {topIssue && (
                <>
                  , most often for <b>{topIssue.issue}</b> (<span className="num">{topIssue.n}</span>)
                </>
              )}
              . The latest fired on {fmtDateLong(latest.feedback_date)}: <b>{latest.issue_category}</b> on {latest.iphone_model}, <span className="num">{fmtNum(latest.curr_3d_avg, 1)}</span>/day against a baseline of <span className="num">{fmtNum(latest.base_14d_avg, 1)}</span>.
            </Lead>
          ) : (
            <Lead>No issue crosses the thresholds in this slice. Loosen them below or widen the date range.</Lead>
          )
        }
      </Loading>

      <div className="grid md:grid-cols-[1fr_auto] gap-8 mb-8 items-start">
        <div className="grid grid-cols-3 gap-6">
          <Kpi label="Alerts" value={fmtInt(rows.length)} size="md" hint={<span>{meta?.gold_rule_alerts} under Gold rule</span>} />
          <Kpi label="Critical (z ≥ 3)" value={fmtInt(rows.filter((r) => r.severity === 'critical').length)} size="md" />
          <Kpi label="Issues affected" value={fmtInt(new Set(rows.map((r) => r.issue_category)).size)} size="md" />
        </div>
        <div className="panel p-4 min-w-[300px]">
          <div className="eyebrow mb-2">Detection rule</div>
          <div className="num text-[12px] text-ink-2 leading-relaxed">
            curr_3d_avg ≥ <b className="text-ink">{minCurr}</b> AND (growth ≥ <b className="text-ink">{minGrowth}%</b> OR z ≥ <b className="text-ink">{minZ}</b>)
          </div>
          <div className="grid grid-cols-[auto_1fr_auto] gap-x-3 gap-y-1.5 mt-3 text-[12px] items-center">
            <span>min z</span>
            <input type="range" min={0} max={5} step={0.5} value={minZ} onChange={(e) => setMinZ(+e.target.value)} />
            <span className="num w-8 text-right">{minZ}</span>
            <span>min growth</span>
            <input type="range" min={0} max={400} step={25} value={minGrowth} onChange={(e) => setMinGrowth(+e.target.value)} />
            <span className="num w-8 text-right">{minGrowth}</span>
            <span>min 3d avg</span>
            <input type="range" min={1} max={6} step={1} value={minCurr} onChange={(e) => setMinCurr(+e.target.value)} />
            <span className="num w-8 text-right">{minCurr}</span>
          </div>
          <div className="flex gap-2 mt-3">
            <Toggle on={excludeUnspec} onChange={setExcludeUnspec} label="Hide unspecified model" />
            {!isDefault && (
              <button
                className="btn"
                onClick={() => {
                  setMinZ(2)
                  setMinGrowth(150)
                  setMinCurr(2)
                }}
              >
                Reset
              </button>
            )}
          </div>
        </div>
      </div>

      <Section title="Where the pressure is" sub="Each cell is the strongest z-score across models for that issue on that day. Stronger colour means further from baseline." evidence={{ br: 'BR03', mart: 'gold_emerging_issues', endpoint: '/emerging/heatmap', ms: heat.data?._ms }}>
        <Loading q={heat} h={260}>
          {() => <Heatmap rows={heat.data!.data} dates={heat.data!.meta.dates} onPick={(issue) => setPick({ issue, model: null })} />}
        </Loading>
      </Section>

      <div className="grid lg:grid-cols-[1fr_1fr] gap-x-10">
        <Section title="Alert feed" sub="Newest first. Click to inspect the series behind it." evidence={{ br: 'BR03', endpoint: '/emerging/alerts', ms: alerts.data?._ms, dbMs: meta?.db_ms, rows: rows.length }}>
          <Loading q={alerts} h={300}>
            {() =>
              rows.length ? (
                <div className="max-h-[560px] overflow-auto -mr-2 pr-2">
                  <table className="data">
                    <thead className="sticky top-0 bg-paper">
                      <tr>
                        <th>Date</th>
                        <th>Issue · model</th>
                        <th className="text-right">3d / base</th>
                        <th className="text-right">Growth</th>
                        <th className="text-right">z</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((r, i) => {
                        const on = pick?.issue === r.issue_category && pick?.model === r.iphone_model
                        return (
                          <tr key={i} className={clsx('cursor-pointer', on && 'bg-surface-2')} onClick={() => setPick({ issue: r.issue_category, model: r.iphone_model })}>
                            <td className="num whitespace-nowrap text-ink-2">{fmtDate(r.feedback_date)}</td>
                            <td>
                              <div className="flex items-center gap-2 flex-wrap">
                                <i className="swatch" style={{ background: issueColor(r.issue_category) }} />
                                <span className="font-medium">{r.issue_category}</span>
                                <span className="text-ink-3 text-[12px]">{r.iphone_model}</span>
                                <Severity level={r.severity} />
                              </div>
                            </td>
                            <td className="num text-right whitespace-nowrap">
                              {fmtNum(r.curr_3d_avg, 1)} <span className="text-ink-3">/ {fmtNum(r.base_14d_avg, 1)}</span>
                            </td>
                            <td className="num text-right">{fmtPct(r.growth_rate_pct, 0, true)}</td>
                            <td className="num text-right text-ink">{fmtNum(r.z_score, 1)}</td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              ) : (
                <Empty />
              )
            }
          </Loading>
        </Section>

        <Section
          title={pick ? `${pick.issue} · ${pick.model ?? 'all models'}` : 'Series inspector'}
          sub={pick ? 'Daily reports with the 3-day current window and 14-day baseline the rule compares.' : 'Pick an alert or a heatmap row.'}
          right={pick && pick.model && <button className="btn" onClick={() => setPick({ issue: pick.issue, model: null })}>All models</button>}
          evidence={pick ? { br: 'BR03', endpoint: '/emerging/series', ms: series.data?._ms } : undefined}
        >
          {pick ? (
            <Loading q={series} h={280}>
              {() => <SeriesChart rows={series.data!.data} issue={pick.issue} />}
            </Loading>
          ) : (
            <Empty>Nothing selected.</Empty>
          )}
        </Section>
      </div>
    </>
  )
}

function Heatmap({ rows, dates, onPick }: { rows: any[]; dates: string[]; onPick: (issue: string) => void }) {
  const t = ink()
  const option = useMemo(() => {
    const data: [number, number, number][] = []
    rows.forEach((r, y) => r.z.forEach((z: number | null, x: number) => z != null && data.push([x, y, z])))
    return {
      grid: { top: 8, bottom: 28, left: 8, right: 8 },
      tooltip: { trigger: 'item', formatter: (p: any) => `<b>${rows[p.value[1]].issue_category}</b><br/>${fmtDate(dates[p.value[0]], 'EEE d MMM')}: z = ${fmtNum(p.value[2], 2)}` },
      xAxis: { data: dates, axisLabel: { formatter: (v: string) => fmtDate(v), interval: 6 }, splitArea: { show: false } },
      yAxis: { type: 'category', data: rows.map((r) => r.issue_category), inverse: true, axisLabel: { color: t.ink2, fontFamily: t.sans, fontSize: 12 }, splitLine: { show: false } },
      visualMap: { min: 0, max: 4, show: false, inRange: { color: [t.surface, ...seq()] } },
      series: [{ type: 'heatmap', data, itemStyle: { borderColor: t.surface, borderWidth: 1 }, emphasis: { itemStyle: { borderColor: t.ink } } }],
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows, dates])
  if (!rows.length) return <Empty />
  return <Chart option={option as any} height={rows.length * 26 + 44} onEvents={{ click: (p) => onPick(rows[p.value[1]].issue_category) }} />
}

function SeriesChart({ rows, issue }: { rows: any[]; issue: string }) {
  const t = ink()
  const c = issueColor(issue)
  const option = {
    grid: { top: 36, bottom: 8 },
    legend: { show: true, top: 0, right: 0, icon: 'rect', itemWidth: 10, itemHeight: 3, textStyle: { color: t.ink2, fontSize: 11 } },
    xAxis: { data: rows.map((r) => r.feedback_date), axisLabel: { formatter: (v: string) => fmtDate(v) } },
    tooltip: {
      formatter: (ps: any[]) => {
        const r = rows[ps[0].dataIndex]
        return `<b>${fmtDateLong(r.feedback_date)}</b><br/>${r.daily_volume} reports · 3d avg ${fmtNum(r.curr_3d_avg, 1)} · base ${fmtNum(r.base_14d_avg, 1)}<br/>growth ${fmtPct(r.growth_rate_pct, 0, true)} · z ${fmtNum(r.z_score, 2)}${r.is_anomaly ? ' · <b>alert</b>' : ''}`
      },
    },
    series: [
      { name: 'daily', type: 'bar', data: rows.map((r) => ({ value: r.daily_volume, itemStyle: { color: r.is_anomaly ? t.accent : t.line2 } })), barMaxWidth: 10, itemStyle: { borderRadius: [2, 2, 0, 0] } },
      { name: '3-day avg', type: 'line', data: rows.map((r) => r.curr_3d_avg), symbol: 'none', lineStyle: { width: 2, color: c } },
      { name: '14-day baseline', type: 'line', data: rows.map((r) => r.base_14d_avg), symbol: 'none', lineStyle: { width: 1.5, color: t.ink3, type: 'dashed' } },
    ],
  }
  const n = rows.filter((r) => r.is_anomaly).length
  return (
    <>
      <Chart option={option as any} height={260} />
      <div className="text-[12px] text-ink-3 mt-1 flex gap-2 items-center">
        <Tag>{n} alert days</Tag> orange bars are days the rule fired
      </div>
    </>
  )
}
