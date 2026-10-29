import { useMemo } from 'react'
import Chart from '../components/Chart'
import FilterBar from '../components/FilterBar'
import { Delta, Empty, Kpi, Lead, Loading, PageHeader, Section, Tag } from '../components/ui'
import { useApi } from '../lib/api'
import { describeSlice, useFilters } from '../lib/filters'
import { fmtDate, fmtDateLong, fmtInt, fmtNum, fmtPct, trendWord } from '../lib/format'
import { ink, issueColor } from '../lib/palette'
import { usePersona } from '../lib/persona'

export default function Overview() {
  const { filters, set } = useFilters()
  const { persona } = usePersona()
  const summary = useApi('/volume/summary', filters)
  const daily = useApi('/volume/daily', filters)
  const weekly = useApi('/volume/weekly', filters)
  const peaks = useApi('/volume/peaks', { ...filters, limit: 6 })

  const s = summary.data?.data?.[0]
  const t = ink()

  const dailyOption = useMemo(() => {
    const rows = daily.data?.data ?? []
    return {
      grid: { top: 36, bottom: 40 },
      tooltip: {
        formatter: (ps: any[]) => {
          const r = rows[ps[0].dataIndex]
          return `<b>${fmtDateLong(r.feedback_date)}</b><br/>${fmtInt(r.total_posts)} posts · ${fmtInt(r.total_comments)} comments<br/>7-day avg ${fmtNum(r.rolling_7d_posts, 1)} posts`
        },
      },
      xAxis: { data: rows.map((r: any) => r.feedback_date), axisLabel: { formatter: (v: string) => fmtDate(v) } },
      yAxis: { name: 'posts / day', nameTextStyle: { color: t.ink3, fontSize: 11, align: 'left' } },
      brush: { toolbox: ['lineX', 'clear'], xAxisIndex: 0, brushStyle: { color: t.accent, opacity: 0.08, borderColor: t.accent } },
      toolbox: { show: true, right: 0, top: -4, itemSize: 13, iconStyle: { borderColor: t.ink3 }, feature: { brush: { title: { lineX: 'Select a date range', clear: 'Clear' } } } },
      series: [
        { type: 'bar', data: rows.map((r: any) => r.total_posts), barMaxWidth: 10, itemStyle: { color: t.line2, borderRadius: [2, 2, 0, 0] }, emphasis: { itemStyle: { color: t.accent } } },
        { type: 'line', data: rows.map((r: any) => r.rolling_7d_posts), smooth: 0.3, symbol: 'none', lineStyle: { width: 2, color: t.accent }, z: 3 },
      ],
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [daily.data])

  const onBrush = {
    brushEnd: (p: any) => {
      const rows = daily.data?.data ?? []
      const area = p.areas?.[0]
      if (!area || !rows.length) return
      const [a, b] = area.coordRange as [number, number]
      const from = rows[Math.max(0, Math.round(a))]?.feedback_date
      const to = rows[Math.min(rows.length - 1, Math.round(b))]?.feedback_date
      if (from && to) set({ date_from: from, date_to: to })
    },
  }

  const commentsOption = useMemo(() => {
    const rows = daily.data?.data ?? []
    return {
      grid: { top: 36, bottom: 8 },
      xAxis: { data: rows.map((r: any) => r.feedback_date), axisLabel: { formatter: (v: string) => fmtDate(v) } },
      yAxis: { name: 'comments / day', nameTextStyle: { color: t.ink3, fontSize: 11, align: 'left' } },
      tooltip: { formatter: (ps: any[]) => `<b>${fmtDateLong(rows[ps[0].dataIndex].feedback_date)}</b><br/>${fmtInt(ps[0].value)} comments` },
      series: [{ type: 'line', data: rows.map((r: any) => r.total_comments), areaStyle: { color: t.line, opacity: 0.6 }, lineStyle: { width: 1.5, color: t.ink2 }, symbol: 'none', smooth: 0.2 }],
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [daily.data])

  const peakRows = peaks.data?.data ?? []

  return (
    <>
      <FilterBar supports={['date_from', 'date_to', 'model', 'ios', 'feature', 'issue']} />
      <PageHeader eyebrow="BR01 · Customer feedback volume" title="How much are people talking?" lead={`${persona.vocabulary.volume} on r/iphone, by day and week, for ${describeSlice(filters)}.`} />

      <Loading q={summary} h={60}>
        {() =>
          s ? (
            <Lead>
              Between {fmtDate(s.range.from, 'd MMM')} and {fmtDate(s.range.to, 'd MMM yyyy')}, r/iphone produced <b className="num">{fmtInt(s.current.posts)}</b> posts and <b className="num">{fmtInt(s.current.comments)}</b> comments
              {s.delta_pct.posts != null && (
                <>
                  , {trendWord(s.delta_pct.posts)} <b className="num">{fmtPct(Math.abs(s.delta_pct.posts), 1)}</b> against the previous {s.range.days} days
                </>
              )}
              . The busiest day was {fmtDateLong(s.peak_day.date)} with <b className="num">{fmtInt(s.peak_day.discussion_units)}</b> discussion units.
            </Lead>
          ) : (
            <Empty />
          )
        }
      </Loading>

      {s && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-x-6 gap-y-5 mb-8 fade-in">
          <Kpi label="Posts" value={fmtInt(s.current.posts)} delta={s.delta_pct.posts} />
          <Kpi label="Comments" value={fmtInt(s.current.comments)} delta={s.delta_pct.comments} />
          <Kpi label="Discussion units" value={fmtInt(s.current.discussion_units)} delta={s.delta_pct.discussion_units} hint={<span>posts + comments</span>} />
          <Kpi label="Posts / day" value={fmtNum(s.current.posts_per_day, 1)} delta={s.delta_pct.posts_per_day} />
          <Kpi label="Avg engagement" value={fmtNum(s.current.avg_engagement, 1)} delta={s.delta_pct.avg_engagement} hint={<span>score + 2×comments</span>} />
        </div>
      )}

      <Section
        title="Daily posts"
        sub="Bars are daily posts; the line is the 7-day average. Drag with the brush tool to set the date range for every page."
        evidence={{ br: 'BR01', mart: daily.data?.meta.source, endpoint: '/volume/daily', ms: daily.data?._ms, dbMs: daily.data?.meta.db_ms, rows: daily.data?.meta.total, cached: !!daily.data?.meta.cache_hits }}
      >
        <Loading q={daily} h={260}>
          {() => (daily.data!.data.length ? <Chart option={dailyOption as any} height={260} onEvents={onBrush} group="overview" /> : <Empty />)}
        </Loading>
      </Section>

      <div className="grid lg:grid-cols-[1.4fr_1fr] gap-x-10">
        <Section title="Daily comments" sub="Comment counts follow posts but spike independently on controversial threads." evidence={{ br: 'BR01', endpoint: '/volume/daily' }}>
          <Loading q={daily} h={200}>
            {() => <Chart option={commentsOption as any} height={200} group="overview" />}
          </Loading>
        </Section>

        <Section title="Week over week" sub="Monday-start weeks; partial weeks are marked." evidence={{ br: 'BR01', endpoint: '/volume/weekly', ms: weekly.data?._ms }}>
          <Loading q={weekly} h={200}>
            {() => {
              const rows = weekly.data!.data as any[]
              const max = Math.max(...rows.map((r) => r.total_posts), 1)
              return (
                <table className="data">
                  <thead>
                    <tr>
                      <th>Week of</th>
                      <th className="text-right">Posts</th>
                      <th className="w-[36%]"></th>
                      <th className="text-right">WoW</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((r) => (
                      <tr key={r.week_start}>
                        <td className="num text-ink-2">
                          {fmtDate(r.week_start)}
                          {r.is_partial && <span className="text-ink-3 text-[10.5px] ml-1">({r.days}d)</span>}
                        </td>
                        <td className="num text-right">{fmtInt(r.total_posts)}</td>
                        <td>
                          <div className="h-[6px] rounded-sm" style={{ width: `${(r.total_posts / max) * 100}%`, background: r.is_partial ? 'var(--line-2)' : 'var(--ink-2)' }} />
                        </td>
                        <td className="text-right">
                          <Delta v={r.wow_growth_pct} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )
            }}
          </Loading>
        </Section>
      </div>

      <Section title="Busiest days" sub="Each peak paired with the loudest negative post of that day, so a spike can be explained in one glance." evidence={{ br: 'BR01 + BR06', endpoint: '/volume/peaks', ms: peaks.data?._ms }}>
        <Loading q={peaks} h={200}>
          {() =>
            peakRows.length ? (
              <table className="data">
                <thead>
                  <tr>
                    <th>Day</th>
                    <th className="text-right">Posts</th>
                    <th className="text-right">Comments</th>
                    <th className="text-right">Units</th>
                    <th>What drove it</th>
                  </tr>
                </thead>
                <tbody>
                  {peakRows.map((r: any) => (
                    <tr key={r.feedback_date}>
                      <td className="whitespace-nowrap">
                        <span className="num">{fmtDate(r.feedback_date, 'd MMM')}</span> <span className="text-ink-3 text-[11px]">{r.weekday}</span>
                      </td>
                      <td className="num text-right">{fmtInt(r.total_posts)}</td>
                      <td className="num text-right">{fmtInt(r.total_comments)}</td>
                      <td className="num text-right text-ink">{fmtInt(r.total_discussion_units)}</td>
                      <td>
                        {r.top_post ? (
                          <div className="flex items-center gap-2 min-w-0">
                            <Tag color={issueColor(r.top_post.issue_category)}>{r.top_post.issue_category}</Tag>
                            <a className="truncate hover:underline" href={`https://www.reddit.com${r.top_post.permalink}`} target="_blank" rel="noreferrer">
                              {r.top_post.title}
                            </a>
                            <span className="num text-ink-3 text-[11px] shrink-0">eng {fmtInt(r.top_post.engagement_score)}</span>
                          </div>
                        ) : (
                          <span className="text-ink-3">no high-impact complaint recorded</span>
                        )}
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
    </>
  )
}
