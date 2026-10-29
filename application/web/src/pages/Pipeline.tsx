import clsx from 'clsx'
import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Empty, Kpi, Lead, Loading, PageHeader, Section, Tag } from '../components/ui'
import { getJson, useApi } from '../lib/api'
import { fmtInt, fmtNum, fmtPct } from '../lib/format'

export default function Pipeline() {
  const ev = useApi('/pipeline/evidence')
  const lat = useApi('/pipeline/latency', {}, { staleTime: 0 })
  const variants = useApi('/meta/variants')
  const fresh = useApi('/meta/freshness')
  const qc = useQueryClient()
  const [probing, setProbing] = useState(false)
  const d = ev.data?.data

  async function probe() {
    setProbing(true)
    const paths = ['/volume/daily', '/volume/summary', '/issues/ranking', '/issues/trends', '/emerging/alerts', '/emerging/heatmap', '/sentiment/timeline', '/sentiment/by-issue', '/features/matrix', '/complaints', '/compare/generations', '/recurring', '/support/demand']
    for (let i = 0; i < 3; i++) for (const p of paths) await getJson(p, i === 1 ? { model: 'iPhone 17' } : i === 2 ? { date_from: '2026-06-01', date_to: '2026-06-30' } : {})
    await qc.invalidateQueries({ queryKey: ['/pipeline/latency'] })
    setProbing(false)
  }

  const modelVariants = variants.data?.data.models ?? {}
  const folded = Object.entries(modelVariants).filter(([, v]) => (v as string[]).length > 1).sort((a, b) => (b[1] as string[]).length - (a[1] as string[]).length)

  return (
    <>
      <PageHeader eyebrow="Evaluation · data correctness, performance, effectiveness" title="Where the numbers come from" lead="The lineage behind every chart, automated consistency checks across the Gold marts, the technology choices with their benchmark figures, and the live latency of this API." />

      <Loading q={ev} h={60}>
        {() =>
          d ? (
            <Lead>
              <b className="num">
                {d.passed} / {d.total_checks}
              </b>{' '}
              correctness checks pass on the serving database: the same <b className="num">{fmtInt(d.checks[0].expected)}</b> Silver posts are counted identically across seven Gold marts and the galaxy fact table, and every emerging-issue flag matches the documented rule.
            </Lead>
          ) : (
            <Empty />
          )
        }
      </Loading>

      <Section title="Lineage" sub="Bronze → Silver → Gold → Serving → Application. Configuration: pyspark_roberta · spark_sql · apache_flink · postgres · galaxy.">
        <Loading q={ev} h={200}>
          {() => (
            <ol className="grid md:grid-cols-3 xl:grid-cols-6 gap-4">
              {d!.lineage.map((s: any, i: number) => (
                <li key={s.stage} className="border-t border-line pt-3">
                  <div className="eyebrow">
                    {i + 1} · {s.stage}
                  </div>
                  <div className="text-[13px] mt-1 leading-snug">{s.tech}</div>
                  <div className="num text-[11px] text-ink-3 mt-1.5 break-words">{s.artifact}</div>
                </li>
              ))}
            </ol>
          )}
        </Loading>
      </Section>

      <div className="grid lg:grid-cols-2 gap-x-10">
        <Section title="Data correctness" sub="Executed live against PostgreSQL on every load of this page." evidence={{ br: 'Evaluation', endpoint: '/pipeline/evidence', ms: ev.data?._ms }}>
          <Loading q={ev} h={260}>
            {() => (
              <table className="data">
                <thead>
                  <tr>
                    <th>Check</th>
                    <th className="text-right">Expected</th>
                    <th className="text-right">Actual</th>
                    <th className="w-16"></th>
                  </tr>
                </thead>
                <tbody>
                  {d!.checks.map((c: any) => (
                    <tr key={c.check}>
                      <td className="text-[12.5px]">{c.check}</td>
                      <td className="num text-right text-ink-2">{fmtInt(c.expected)}</td>
                      <td className="num text-right">{fmtInt(c.actual)}</td>
                      <td className={clsx('text-right font-medium text-[12px]', c.passed ? 'text-pos' : 'text-neg')}>{c.passed ? '✓ pass' : '✗ fail'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Loading>
        </Section>

        <Section title="Data quality notes" sub="Known limitations of the current Silver extractor, and how the application copes.">
          <Loading q={ev} h={260}>
            {() => (
              <>
                <div className="grid grid-cols-2 gap-x-6 gap-y-4 mb-4">
                  <Kpi label="Raw model labels" value={d!.quality.raw_model_labels} size="md" bare hint={<span>→ {d!.quality.canonical_model_labels} after folding</span>} />
                  <Kpi label="Raw iOS labels" value={d!.quality.raw_ios_labels} size="md" bare hint={<span>→ {d!.quality.canonical_ios_labels} after folding</span>} />
                  <Kpi label="No model named" value={fmtPct(d!.quality.unspecified_model_share_pct, 0)} size="md" bare />
                  <Kpi label="No iOS named" value={fmtPct(d!.quality.unspecified_ios_share_pct, 0)} size="md" bare />
                  <Kpi label="General discussion" value={fmtPct(d!.quality.non_defect_share_pct, 0)} size="md" bare hint={<span>of all posts</span>} />
                  <Kpi label="Non-defect in BR06 top 500" value={d!.quality.non_defect_in_high_impact} size="md" bare />
                </div>
                <div className="text-[12.5px] text-ink-2 leading-relaxed space-y-2">
                  <p>
                    The regex extractor keeps the matched string as written (“iPhone 13Pro”, “İphone 13”, “iPhone16 Promax”) and accepts products that do not exist (“iPhone 3 Pro”, “iOS 24.5”). The API folds spelling variants into one canonical label and sends impossible products to <em>Other / Unspecified</em> before anything is aggregated; filters are expanded back to the raw spellings at query time.
                  </p>
                  {folded.length > 0 && (
                    <details>
                      <summary className="cursor-pointer text-ink">Largest folds ({folded.length} labels with variants)</summary>
                      <ul className="mt-2 space-y-1 num text-[11.5px] text-ink-3">
                        {folded.slice(0, 10).map(([k, v]) => (
                          <li key={k}>
                            <span className="text-ink-2">{k}</span> ← {(v as string[]).join(', ')}
                          </li>
                        ))}
                      </ul>
                    </details>
                  )}
                  <p>Fix planned upstream: normalise in the Silver extractor and exclude general discussion from the BR06 mart, then re-run Silver → Gold → Serving. The folding layer then becomes an identity mapping.</p>
                </div>
              </>
            )}
          </Loading>
        </Section>
      </div>

      <Section
        title="API performance"
        sub="Measured inside this process since start-up. DB time is what PostgreSQL took; the rest is pandas re-aggregation and serialisation."
        right={
          <button className="btn" onClick={probe} disabled={probing}>
            {probing ? 'Probing…' : 'Run 39-request probe'}
          </button>
        }
        evidence={{ br: 'Evaluation', endpoint: '/pipeline/latency' }}
      >
        <Loading q={lat} h={200}>
          {() => {
            const l = lat.data!.data
            return l.requests ? (
              <>
                <div className="grid grid-cols-4 gap-6 mb-4">
                  <Kpi label="Requests" value={fmtInt(l.requests)} size="md" bare />
                  <Kpi label="p50" value={`${fmtNum(l.overall.p50_ms, 0)} ms`} size="md" bare />
                  <Kpi label="p95" value={`${fmtNum(l.overall.p95_ms, 0)} ms`} size="md" bare />
                  <Kpi label="p99" value={`${fmtNum(l.overall.p99_ms, 0)} ms`} size="md" bare />
                </div>
                <table className="data">
                  <thead>
                    <tr>
                      <th>Route</th>
                      <th className="text-right">n</th>
                      <th className="text-right">p50</th>
                      <th className="text-right">p95</th>
                      <th className="text-right">p99</th>
                      <th className="text-right">DB mean</th>
                      <th className="text-right">Cache hit</th>
                    </tr>
                  </thead>
                  <tbody>
                    {l.routes.map((r: any) => (
                      <tr key={r.route}>
                        <td className="num text-[12.5px]">{r.route}</td>
                        <td className="num text-right text-ink-3">{r.n}</td>
                        <td className="num text-right">{fmtNum(r.p50_ms, 0)}</td>
                        <td className="num text-right">{fmtNum(r.p95_ms, 0)}</td>
                        <td className="num text-right">{fmtNum(r.p99_ms, 0)}</td>
                        <td className="num text-right text-ink-2">{fmtNum(r.db_mean_ms, 0)}</td>
                        <td className="num text-right text-ink-2">{fmtPct(r.cache_hit_rate_pct, 0)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </>
            ) : (
              <Empty action={<button className="btn" onClick={probe}>Run probe</button>}>No requests recorded yet in this API process.</Empty>
            )
          }}
        </Loading>
      </Section>

      <Section title="Business requirement coverage" sub="Every requirement maps to one Gold mart, at least one endpoint and one page. This is the effectiveness evidence for the report.">
        <Loading q={ev} h={260}>
          {() => (
            <table className="data">
              <thead>
                <tr>
                  <th>BR</th>
                  <th>Requirement</th>
                  <th>Users</th>
                  <th>Gold mart</th>
                  <th>Endpoints</th>
                  <th>Page</th>
                </tr>
              </thead>
              <tbody>
                {d!.br_matrix.map((b: any) => (
                  <tr key={b.id}>
                    <td className="num font-medium">{b.id}</td>
                    <td>{b.name}</td>
                    <td className="text-[12px] text-ink-2">{b.users.join(', ')}</td>
                    <td className="num text-[12px]">{b.mart}</td>
                    <td className="num text-[11.5px] text-ink-2">{b.endpoints.join(' ')}</td>
                    <td>
                      <a className="hover:underline" href={b.page}>
                        {b.page}
                      </a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Loading>
      </Section>

      <Section title="Technology choices and alternatives" sub="Main technology per stage with the alternatives benchmarked by the data engineering team (tests/pipeline_benchmark.py).">
        <Loading q={ev} h={200}>
          {() => {
            const b = d!.benchmark
            return (
              <div className="grid md:grid-cols-2 xl:grid-cols-4 gap-6 text-[12.5px]">
                <BenchCol title="Batch gold engine" rows={b.batch_gold} nameKey="engine" />
                <BenchCol title="Stream engine (BR03)" rows={b.stream} nameKey="engine" />
                <BenchCol title="Serving backend" rows={b.serving} nameKey="backend" />
                <BenchCol title="Schema paradigm" rows={b.schema} nameKey="paradigm" />
                <div className="col-span-full text-[11.5px] text-ink-3">Source: {b.source}. Serving snapshot: {fresh.data ? Object.values(fresh.data.data.row_counts as Record<string, number>).reduce((a, n) => a + n, 0).toLocaleString() : '…'} rows across ten gold_* tables.</div>
              </div>
            )
          }}
        </Loading>
      </Section>
    </>
  )
}

function BenchCol({ title, rows, nameKey }: { title: string; rows: any[]; nameKey: string }) {
  return (
    <div>
      <div className="eyebrow mb-2">{title}</div>
      <ul className="space-y-1.5">
        {rows.map((r, i) => (
          <li key={r[nameKey]} className="flex flex-wrap items-baseline gap-x-2">
            <span className={clsx('num', i === 0 ? 'text-ink font-medium' : 'text-ink-2')}>{r[nameKey]}</span>
            {i === 0 && <Tag>main</Tag>}
            <span className="text-ink-3 text-[11.5px]">
              {Object.entries(r)
                .filter(([k]) => k !== nameKey && k !== 'note')
                .map(([k, v]) => `${k.replace(/_/g, ' ')} ${typeof v === 'number' ? v.toLocaleString() : v}`)
                .join(' · ')}
              {r.note ? ` ${r.note}` : ''}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}
