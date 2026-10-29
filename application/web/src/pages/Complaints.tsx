import { useState } from 'react'
import FilterBar from '../components/FilterBar'
import { Bar, Empty, Kpi, Lead, Loading, PageHeader, Section, Tag, Toggle } from '../components/ui'
import { useApi } from '../lib/api'
import { describeSlice, useFilters } from '../lib/filters'
import { fmtDate, fmtInt, fmtNum } from '../lib/format'
import { issueColor } from '../lib/palette'

const SORTS = [
  { v: 'impact', label: 'Impact index' },
  { v: 'engagement', label: 'Engagement' },
  { v: 'score', label: 'Reddit score' },
  { v: 'comments', label: 'Comments' },
  { v: 'recent', label: 'Most recent' },
  { v: 'sentiment', label: 'Most negative' },
]

export default function Complaints() {
  const { filters } = useFilters()
  const [sort, setSort] = useState('impact')
  const [q, setQ] = useState('')
  const [hideGeneral, setHideGeneral] = useState(true)
  const [page, setPage] = useState(0)
  const limit = 20
  const res = useApi('/complaints', { ...filters, sort, q: q || undefined, include_non_defect: !hideGeneral, limit, offset: page * limit })
  const rows: any[] = res.data?.data ?? []
  const meta = res.data?.meta
  const total = meta?.total ?? 0
  const pages = Math.max(1, Math.ceil(total / limit))
  const top = rows[0]
  const maxImpact = Math.max(...rows.map((r) => r.impact_index), 1)
  const byIssue: any[] = meta?.by_issue ?? []
  const maxReach = Math.max(...byIssue.map((b) => b.reach), 1)

  return (
    <>
      <FilterBar supports={['date_from', 'date_to', 'model', 'ios', 'feature', 'issue']} />
      <PageHeader
        eyebrow="BR06 · High-impact complaint identification"
        title="Which complaints are the loudest?"
        lead={`The 500 most-engaged negative posts, ranked by impact index (log engagement × upvote agreement) for ${describeSlice(filters)}. Each row links back to the thread on Reddit.`}
        aside={
          <div className="flex gap-2 flex-wrap justify-end">
            <input className="field w-48" placeholder="Search titles…" value={q} onChange={(e) => (setQ(e.target.value), setPage(0))} />
            <select className="field" value={sort} onChange={(e) => (setSort(e.target.value), setPage(0))}>
              {SORTS.map((s) => (
                <option key={s.v} value={s.v}>
                  Sort: {s.label}
                </option>
              ))}
            </select>
            <Toggle on={hideGeneral} onChange={(v) => (setHideGeneral(v), setPage(0))} label="Defects only" />
          </div>
        }
      />

      <Loading q={res} h={60}>
        {() =>
          top ? (
            <Lead>
              <b className="num">{fmtInt(total)}</b> {hideGeneral ? 'defect complaints' : 'negative posts'} reached <b className="num">{fmtInt(meta?.summary.reach)}</b> engagement points in total. The strongest is “{top.title}” — <b>{top.issue_category}</b>, score <span className="num">{fmtInt(top.reddit_score)}</span> with <span className="num">{fmtInt(top.num_comments)}</span> comments.
            </Lead>
          ) : (
            <Lead>No complaints match this slice.</Lead>
          )
        }
      </Loading>

      <div className="grid lg:grid-cols-[1fr_300px] gap-x-10">
        <Section title="Complaint list" sub={`Page ${page + 1} of ${pages}. Impact bar is relative to the page.`} evidence={{ br: 'BR06', mart: 'gold_high_impact_complaints', endpoint: '/complaints', ms: res.data?._ms, dbMs: meta?.db_ms, rows: total }}>
          <Loading q={res} h={400}>
            {() =>
              rows.length ? (
                <>
                  <table className="data">
                    <thead>
                      <tr>
                        <th className="w-8">#</th>
                        <th>Post</th>
                        <th className="text-right">Score</th>
                        <th className="text-right">Cmts</th>
                        <th className="w-[14%]">Impact</th>
                        <th className="text-right">Sent.</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((r, i) => (
                        <tr key={r.post_id}>
                          <td className="num text-ink-3">{page * limit + i + 1}</td>
                          <td>
                            <a href={r.reddit_url} target="_blank" rel="noreferrer" className="block text-[13.5px] text-ink hover:underline leading-snug">
                              {r.title}
                            </a>
                            <div className="flex flex-wrap items-center gap-x-2 gap-y-1 mt-1 text-[11.5px] text-ink-3">
                              <Tag color={issueColor(r.issue_category)}>{r.issue_category}</Tag>
                              {r.iphone_model !== 'Other / Unspecified' && <span>{r.iphone_model}</span>}
                              {r.ios_version !== 'iOS Unspecified' && <span>{r.ios_version}</span>}
                              <span className="num">{fmtDate(r.feedback_date, 'd MMM yyyy')}</span>
                            </div>
                          </td>
                          <td className="num text-right">{fmtInt(r.reddit_score)}</td>
                          <td className="num text-right">{fmtInt(r.num_comments)}</td>
                          <td>
                            <div className="flex items-center gap-2">
                              <Bar pct={(r.impact_index / maxImpact) * 100} color="var(--ink-2)" />
                              <span className="num text-[11.5px] text-ink-2 w-9 text-right">{fmtNum(r.impact_index, 1)}</span>
                            </div>
                          </td>
                          <td className="num text-right text-neg">{fmtNum(r.sentiment_score, 2)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <div className="flex items-center justify-between mt-3 text-[12.5px]">
                    <button className="btn" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>
                      ← Newer rank
                    </button>
                    <span className="num text-ink-3">
                      {page * limit + 1}–{Math.min(total, (page + 1) * limit)} of {total}
                    </span>
                    <button className="btn" disabled={page >= pages - 1} onClick={() => setPage((p) => p + 1)}>
                      Lower rank →
                    </button>
                  </div>
                </>
              ) : (
                <Empty />
              )
            }
          </Loading>
        </Section>

        <div>
          <Section title="Reach by issue" sub="Total engagement of complaints in this slice." evidence={{ br: 'BR06', endpoint: '/complaints' }}>
            <div className="grid grid-cols-2 gap-4 mb-4">
              <Kpi label="Complaints" value={fmtInt(total)} size="md" bare />
              <Kpi label="Avg impact" value={fmtNum(meta?.summary.avg_impact, 2)} size="md" bare />
            </div>
            {byIssue.length ? (
              <div className="space-y-2">
                {byIssue.map((b) => (
                  <div key={b.issue}>
                    <div className="flex justify-between text-[12.5px]">
                      <span className="truncate">{b.issue}</span>
                      <span className="num text-ink-3">
                        {b.n} · {fmtInt(b.reach)}
                      </span>
                    </div>
                    <Bar pct={(b.reach / maxReach) * 100} color={issueColor(b.issue)} />
                  </div>
                ))}
              </div>
            ) : (
              <Empty />
            )}
          </Section>
          <div className="text-[12px] text-ink-3 leading-relaxed">
            <div className="eyebrow mb-1">How impact is computed</div>
            <code className="num block text-[11.5px]">engagement = score + 2 × comments</code>
            <code className="num block text-[11.5px]">impact = ln(1 + engagement) × (0.5 + 0.5 × upvote_ratio)</code>
            <p className="mt-2">Only posts the RoBERTa model scored negative are eligible. “Defects only” drops posts the taxonomy filed under general discussion; they are the most up-voted threads but rarely actionable.</p>
          </div>
        </div>
      </div>
    </>
  )
}
