import { useMemo } from 'react'
import Chart from '../components/Chart'
import FilterBar from '../components/FilterBar'
import { Bar, Delta, Empty, IssueLink, Kpi, Lead, Loading, PageHeader, Section, Tag } from '../components/ui'
import { useApi } from '../lib/api'
import { describeSlice, useFilters } from '../lib/filters'
import { fmtInt, fmtMonth, fmtNum, fmtPct } from '../lib/format'
import { ink, issueColor, seq } from '../lib/palette'

export default function Support() {
  const { filters } = useFilters()
  const recurring = useApi('/recurring', { issue: filters.issue })
  const demand = useApi('/support/demand', { model: filters.model, ios: filters.ios })
  const rec: any[] = recurring.data?.data ?? []
  const periods: string[] = recurring.data?.meta.periods ?? []
  const cats: any[] = demand.data?.data ?? []
  const dm = demand.data?.meta
  const t = ink()

  const recurringCount = rec.filter((r) => r.is_recurring).length
  const mostVolatile = useMemo(() => [...rec].filter((r) => r.volatility_pct != null && r.total >= 30).sort((a, b) => b.volatility_pct - a.volatility_pct)[0], [rec])
  const risingCat = useMemo(() => [...cats].filter((c) => c.period_delta_pct != null && c.question_count >= 50).sort((a, b) => b.period_delta_pct - a.period_delta_pct)[0], [cats])

  const demandLines = useMemo(() => {
    const ps: string[] = dm?.periods ?? []
    const top = cats.slice(0, 6)
    const ramp = seq()
    return {
      grid: { top: 36, bottom: 56 },
      legend: { show: true, bottom: 0, left: 0, icon: 'rect', itemWidth: 10, itemHeight: 3, textStyle: { color: t.ink2, fontSize: 11 } },
      xAxis: { data: ps, axisLabel: { formatter: (v: string) => fmtMonth(v) }, boundaryGap: false },
      yAxis: { name: 'questions / month', nameTextStyle: { color: t.ink3, fontSize: 11, align: 'left' } },
      tooltip: { formatter: (p: any[]) => `<b>${fmtMonth(p[0].axisValue)}</b><br/>` + p.map((x) => `<span style="color:${x.color}">■</span> ${x.seriesName}: ${fmtInt(x.value)}`).join('<br/>') },
      series: top.map((c, i) => ({ name: c.support_category, type: 'line', data: c.by_period, symbol: 'circle', symbolSize: 6, lineStyle: { width: 2, color: ramp[4 - Math.min(i, 4)] }, itemStyle: { color: ramp[4 - Math.min(i, 4)] } })),
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cats, dm])

  return (
    <>
      <FilterBar supports={['model', 'ios', 'issue']} />
      <PageHeader
        eyebrow="BR09 · Recurring issue monitoring  —  BR10 · Support demand analysis"
        title="What keeps coming back, and what do people ask for help with?"
        lead={`Month-level views that outlive single spikes: defects that recur across months and the questions people bring to the community, for ${describeSlice(filters)}.`}
      />

      <Loading q={recurring} h={60}>
        {() =>
          rec.length ? (
            <Lead>
              <b className="num">{recurringCount}</b> of <b className="num">{rec.length}</b> defect categories appear in two or more months, which makes them structural rather than incidental.
              {mostVolatile && (
                <>
                  {' '}
                  <b>{mostVolatile.issue_category}</b> swings the most month to month (<span className="num">±{fmtPct(mostVolatile.volatility_pct, 0)}</span>), peaking in {fmtMonth(mostVolatile.max_period)}.
                </>
              )}
            </Lead>
          ) : (
            <Empty />
          )
        }
      </Loading>

      <Section title="Recurring defects by month" sub="Cell shade follows the count. Volatility is the coefficient of variation across months." evidence={{ br: 'BR09', mart: 'gold_recurring_issues', endpoint: '/recurring', ms: recurring.data?._ms, dbMs: recurring.data?.meta.db_ms, rows: rec.length }}>
        <Loading q={recurring} h={300}>
          {() =>
            rec.length ? (
              <table className="data">
                <thead>
                  <tr>
                    <th>Issue</th>
                    {periods.map((p) => (
                      <th key={p} className="text-right">
                        {fmtMonth(p)}
                      </th>
                    ))}
                    <th className="text-right">Total</th>
                    <th className="text-right">Months</th>
                    <th className="text-right">Volatility</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {rec.map((r) => {
                    const max = Math.max(...rec.flatMap((x) => x.counts.map((c: number | null) => c ?? 0)), 1)
                    return (
                      <tr key={r.issue_category}>
                        <td>
                          <span className="inline-flex items-center gap-2">
                            <i className="swatch" style={{ background: issueColor(r.issue_category) }} />
                            <IssueLink issue={r.issue_category} />
                          </span>
                        </td>
                        {r.counts.map((c: number | null, i: number) => (
                          <td key={i} className="text-right">
                            {c == null ? (
                              <span className="text-ink-3">·</span>
                            ) : (
                              <span className="inline-block min-w-[48px] px-1.5 py-0.5 rounded-sm num text-right" style={{ background: `color-mix(in oklab, var(--seq-4) ${Math.round((c / max) * 70)}%, transparent)`, color: c / max > 0.6 ? '#fff' : 'inherit' }}>
                                {fmtInt(c)}
                              </span>
                            )}
                          </td>
                        ))}
                        <td className="num text-right">{fmtInt(r.total)}</td>
                        <td className="num text-right text-ink-2">{r.active_period_count}</td>
                        <td className="num text-right text-ink-2">{r.volatility_pct == null ? '–' : `±${fmtPct(r.volatility_pct, 0)}`}</td>
                        <td>{r.is_recurring ? <Tag>recurring</Tag> : <span className="text-ink-3 text-[11.5px]">one-off</span>}</td>
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

      <Loading q={demand} h={60}>
        {() =>
          cats.length ? (
            <Lead>
              <b className="num">{fmtInt(dm?.total_questions)}</b> posts were questions asking for help; <b>{cats[0].support_category}</b> is the largest bucket at <b className="num">{fmtPct(cats[0].share_pct, 0)}</b>
              {risingCat && risingCat.period_delta_pct > 5 && (
                <>
                  , and <b>{risingCat.support_category}</b> grew <b className="num">{fmtPct(risingCat.period_delta_pct, 0)}</b> in the latest month
                </>
              )}
              .
            </Lead>
          ) : null
        }
      </Loading>

      <div className="grid lg:grid-cols-[1fr_1fr] gap-x-10">
        <Section title="Support demand by category" sub="Questions per support category with month-over-month change." evidence={{ br: 'BR10', mart: 'gold_support_demand', endpoint: '/support/demand', ms: demand.data?._ms, dbMs: dm?.db_ms, rows: cats.length }}>
          <Loading q={demand} h={300}>
            {() =>
              cats.length ? (
                <>
                  <div className="grid grid-cols-3 gap-4 mb-4">
                    <Kpi label="Questions" value={fmtInt(dm?.total_questions)} size="md" bare />
                    <Kpi label="Categories" value={cats.length} size="md" bare />
                    <Kpi label="No model named" value={fmtPct((dm!.unspecified_model_questions / dm!.total_questions) * 100, 0)} size="md" bare />
                  </div>
                  <table className="data">
                    <thead>
                      <tr>
                        <th>Category</th>
                        <th className="text-right">Questions</th>
                        <th className="w-[28%]">Share</th>
                        <th className="text-right">Sent.</th>
                        <th className="text-right">Latest MoM</th>
                      </tr>
                    </thead>
                    <tbody>
                      {cats.map((c) => (
                        <tr key={c.support_category}>
                          <td>{c.support_category}</td>
                          <td className="num text-right">{fmtInt(c.question_count)}</td>
                          <td>
                            <div className="flex items-center gap-2">
                              <Bar pct={c.share_pct} color="var(--seq-4)" />
                              <span className="num text-[11.5px] text-ink-2 w-10 text-right">{fmtPct(c.share_pct, 0)}</span>
                            </div>
                          </td>
                          <td className="num text-right text-ink-2">{fmtNum(c.avg_sentiment_score, 2)}</td>
                          <td className="text-right">
                            <Delta v={c.period_delta_pct} invert />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </>
              ) : (
                <Empty />
              )
            }
          </Loading>
        </Section>

        <div>
          <Section title="Demand over months" sub="Top six categories, one hue ramp (darker = larger category)." evidence={{ br: 'BR10', endpoint: '/support/demand' }}>
            <Loading q={demand} h={240}>
              {() => (cats.length ? <Chart option={demandLines as any} height={240} /> : <Empty />)}
            </Loading>
          </Section>
          <Section title="Who is asking" sub="Models with the most support questions and their dominant topic." evidence={{ br: 'BR10', endpoint: '/support/demand' }}>
            <Loading q={demand} h={200}>
              {() =>
                dm?.by_model?.length ? (
                  <table className="data">
                    <thead>
                      <tr>
                        <th>Model</th>
                        <th className="text-right">Questions</th>
                        <th>Top topic</th>
                      </tr>
                    </thead>
                    <tbody>
                      {dm.by_model.map((m: any) => (
                        <tr key={m.iphone_model}>
                          <td>{m.iphone_model}</td>
                          <td className="num text-right">{fmtInt(m.question_count)}</td>
                          <td className="text-ink-2">
                            {m.top_category} <span className="num text-ink-3 text-[11px]">{fmtInt(m.categories[m.top_category])}</span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <Empty />
                )
              }
            </Loading>
          </Section>
        </div>
      </div>
    </>
  )
}
