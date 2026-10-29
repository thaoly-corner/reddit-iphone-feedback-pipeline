import { useMemo, useState } from 'react'
import Chart from '../components/Chart'
import FilterBar from '../components/FilterBar'
import { Empty, Kpi, Lead, Loading, PageHeader, Section, Segmented, StackBar, Tag, Toggle } from '../components/ui'
import { useApi } from '../lib/api'
import { describeSlice, useFilters } from '../lib/filters'
import { fmtDate, fmtDateLong, fmtInt, fmtNum, fmtPct } from '../lib/format'
import { ink, issueColor, sentimentColor } from '../lib/palette'

export default function Sentiment() {
  const { filters } = useFilters()
  const [gran, setGran] = useState<'day' | 'week'>('day')
  const [general, setGeneral] = useState(true)
  const timeline = useApi('/sentiment/timeline', { ...filters, granularity: gran })
  const byIssue = useApi('/sentiment/by-issue', { ...filters, include_general: general })
  const byModel = useApi('/sentiment/by-model', { ...filters, min_posts: 30 })

  const rows: any[] = timeline.data?.data ?? []
  const overall = timeline.data?.meta.overall
  const t = ink()
  const pos = sentimentColor('POSITIVE'),
    neu = sentimentColor('NEUTRAL'),
    neg = sentimentColor('NEGATIVE')

  const first = rows[0],
    last = rows[rows.length - 1]
  const drift = first && last ? last.net_7d - first.net_7d : null

  const shareOption = useMemo(
    () => ({
      grid: { top: 40, bottom: 8 },
      legend: { show: true, top: 0, right: 0, icon: 'rect', itemWidth: 10, itemHeight: 10, textStyle: { color: t.ink2, fontSize: 11 } },
      xAxis: { data: rows.map((r) => r.feedback_date), axisLabel: { formatter: (v: string) => fmtDate(v) } },
      yAxis: { max: 100, axisLabel: { formatter: '{value}%' } },
      tooltip: {
        formatter: (ps: any[]) => {
          const r = rows[ps[0].dataIndex]
          return `<b>${fmtDateLong(r.feedback_date)}</b><br/>positive ${fmtPct(r.positive_pct, 0)} · neutral ${fmtPct(100 - r.positive_pct - r.negative_pct, 0)} · negative ${fmtPct(r.negative_pct, 0)}<br/>${fmtInt(r.total)} posts`
        },
      },
      series: [
        { name: 'Negative', type: 'line', stack: 's', areaStyle: { color: neg, opacity: 0.85 }, lineStyle: { width: 0 }, symbol: 'none', data: rows.map((r) => r.negative_pct), itemStyle: { color: neg } },
        { name: 'Neutral', type: 'line', stack: 's', areaStyle: { color: neu, opacity: 0.45 }, lineStyle: { width: 0 }, symbol: 'none', data: rows.map((r) => +(100 - r.positive_pct - r.negative_pct).toFixed(2)), itemStyle: { color: neu } },
        { name: 'Positive', type: 'line', stack: 's', areaStyle: { color: pos, opacity: 0.85 }, lineStyle: { width: 0 }, symbol: 'none', data: rows.map((r) => r.positive_pct), itemStyle: { color: pos } },
      ],
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [rows],
  )

  const netOption = useMemo(
    () => ({
      grid: { top: 36, bottom: 8 },
      xAxis: { data: rows.map((r) => r.feedback_date), axisLabel: { formatter: (v: string) => fmtDate(v) } },
      yAxis: { name: 'net sentiment (pos − neg) %', nameTextStyle: { color: t.ink3, fontSize: 11, align: 'left' }, axisLabel: { formatter: '{value}%' } },
      tooltip: { formatter: (ps: any[]) => `<b>${fmtDateLong(rows[ps[0].dataIndex].feedback_date)}</b><br/>net ${fmtPct(rows[ps[0].dataIndex].net_sentiment_pct, 1)} · smoothed ${fmtPct(ps[1]?.value ?? ps[0].value, 1)}` },
      series: [
        { type: 'bar', data: rows.map((r) => ({ value: r.net_sentiment_pct, itemStyle: { color: r.net_sentiment_pct >= 0 ? pos : neg, opacity: 0.35 } })), barMaxWidth: 10 },
        { type: 'line', data: rows.map((r) => r.net_7d), symbol: 'none', lineStyle: { width: 2, color: t.ink }, smooth: 0.2 },
      ],
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [rows],
  )

  return (
    <>
      <FilterBar supports={['date_from', 'date_to', 'model', 'ios', 'feature', 'issue']} />
      <PageHeader
        eyebrow="BR04 · Customer sentiment analysis"
        title="How do people feel?"
        lead={`RoBERTa-scored sentiment (cardiffnlp/twitter-roberta-base-sentiment-latest) on every post, aggregated by day, issue and model for ${describeSlice(filters)}.`}
        aside={<Segmented value={gran} options={[{ v: 'day', label: 'Daily' }, { v: 'week', label: 'Weekly' }]} onChange={setGran} />}
      />

      <Loading q={timeline} h={60}>
        {() =>
          overall ? (
            <Lead>
              Net sentiment sits at <b className="num">{fmtPct(overall.net_sentiment_pct, 1, true)}</b>: <b className="num">{fmtPct(overall.negative_pct, 0)}</b> of posts are negative, which is typical for a support-heavy subreddit.
              {drift != null && Math.abs(drift) >= 2 && (
                <>
                  {' '}
                  The smoothed line {drift > 0 ? 'improved' : 'deteriorated'} by <b className="num">{fmtNum(Math.abs(drift), 1)} pts</b> across the range.
                </>
              )}
            </Lead>
          ) : (
            <Empty />
          )
        }
      </Loading>

      {overall && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6 mb-8">
          <Kpi label="Net sentiment" value={fmtPct(overall.net_sentiment_pct, 1, true)} size="md" />
          <Kpi label="Positive" value={fmtInt(overall.positive)} size="md" hint={<span className="num">{fmtPct((overall.positive / (overall.positive + overall.neutral + overall.negative)) * 100, 1)}</span>} />
          <Kpi label="Neutral" value={fmtInt(overall.neutral)} size="md" />
          <Kpi label="Negative" value={fmtInt(overall.negative)} size="md" hint={<span className="num">{fmtPct(overall.negative_pct, 1)}</span>} />
        </div>
      )}

      <Section title="Sentiment mix over time" sub="Share of posts per day. Stacked so the eye reads the negative band against the whole." evidence={{ br: 'BR04', mart: timeline.data?.meta.source, endpoint: '/sentiment/timeline', ms: timeline.data?._ms, dbMs: timeline.data?.meta.db_ms, rows: rows.length }}>
        <Loading q={timeline} h={260}>
          {() => (rows.length ? <Chart option={shareOption as any} height={260} group="sent" /> : <Empty />)}
        </Loading>
      </Section>

      <Section title="Net sentiment" sub="Positive minus negative share. Bars are raw days; the line is a 7-day mean." evidence={{ br: 'BR04', endpoint: '/sentiment/timeline' }}>
        <Loading q={timeline} h={200}>
          {() => (rows.length ? <Chart option={netOption as any} height={200} group="sent" /> : <Empty />)}
        </Loading>
      </Section>

      <div className="grid lg:grid-cols-2 gap-x-10">
        <Section title="By issue" sub="Which problems carry the most negative weight." right={<Toggle on={general} onChange={setGeneral} label="General discussion" />} evidence={{ br: 'BR04', mart: 'gold_issue_summary', endpoint: '/sentiment/by-issue', ms: byIssue.data?._ms }}>
          <Loading q={byIssue} h={300}>
            {() => <MixTable rows={byIssue.data!.data} nameKey="issue_category" colorOf={(r) => issueColor(r.issue_category)} />}
          </Loading>
        </Section>
        <Section title="By iPhone model" sub="Models with at least 30 posts. Raw spelling variants are folded together." evidence={{ br: 'BR04', mart: 'gold_sentiment_summary', endpoint: '/sentiment/by-model', ms: byModel.data?._ms }}>
          <Loading q={byModel} h={300}>
            {() => <MixTable rows={byModel.data!.data} nameKey="iphone_model" />}
          </Loading>
        </Section>
      </div>
    </>
  )
}

function MixTable({ rows, nameKey, colorOf }: { rows: any[]; nameKey: string; colorOf?: (r: any) => string }) {
  if (!rows.length) return <Empty />
  const pos = sentimentColor('POSITIVE'),
    neu = sentimentColor('NEUTRAL'),
    neg = sentimentColor('NEGATIVE')
  return (
    <>
      <table className="data">
        <thead>
          <tr>
            <th>{nameKey === 'iphone_model' ? 'Model' : 'Issue'}</th>
            <th className="text-right">Posts</th>
            <th className="w-[38%]">Mix</th>
            <th className="text-right">Net</th>
            <th className="text-right">Mean score</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r[nameKey]}>
              <td>
                <div className="flex items-center gap-2">
                  {colorOf && <i className="swatch" style={{ background: colorOf(r) }} />}
                  <span>{r[nameKey]}</span>
                </div>
              </td>
              <td className="num text-right">{fmtInt(r.total)}</td>
              <td>
                <StackBar
                  parts={[
                    { v: r.positive, color: pos, label: 'positive' },
                    { v: r.neutral, color: neu, label: 'neutral' },
                    { v: r.negative, color: neg, label: 'negative' },
                  ]}
                />
              </td>
              <td className="num text-right" style={{ color: r.net_sentiment_pct >= 0 ? pos : neg }}>
                {fmtPct(r.net_sentiment_pct, 0, true)}
              </td>
              <td className="num text-right text-ink-2">{r.mean_sentiment_score != null ? fmtNum(r.mean_sentiment_score, 2) : '–'}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="flex gap-2 mt-2 text-[11.5px]">
        <Tag color={pos}>positive</Tag>
        <Tag color={neu}>neutral</Tag>
        <Tag color={neg}>negative</Tag>
      </div>
    </>
  )
}
