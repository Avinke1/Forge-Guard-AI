import React from 'react';
import { Link } from 'react-router-dom';
import { Gauge, ArrowRight } from 'lucide-react';
import { Machine, PriorityLevel } from '../types';
import { USE_MOCK } from '../api';
import { PriorityBadge } from './PriorityBadge';

/**
 * "What ForgeGuard did" - a summary of the current analysis run.
 * Every value comes from the machines that api.ts already returns; anything missing shows "-".
 */

const LEVELS: PriorityLevel[] = ['HIGH', 'MEDIUM', 'LOW', 'OK'];

interface ImpactPanelProps {
  machines: Machine[];
  loading?: boolean;
}

export const ImpactPanel: React.FC<ImpactPanelProps> = ({ machines, loading = false }) => {
  const hasData = !loading && machines.length > 0;
  const readingCounts = machines.map((m) => m.readingsCount).filter((n) => Number.isFinite(n));
  const totalReadings = hasData && readingCounts.length === machines.length ? readingCounts.reduce((a, b) => a + b, 0) : null;
  const count = (level: PriorityLevel) => (hasData ? machines.filter((m) => m.priority === level).length : null);
  // The queue is already ranked; the first machine that needs any inspection is the one to inspect first.
  const top = hasData
    ? [...machines].sort((a, b) => a.rank - b.rank).find((m) => m.priority !== 'OK') ?? null
    : null;

  const show = (v: number | null) => (v === null ? '-' : v.toLocaleString());

  return (
    <section
      aria-labelledby="impact-heading"
      className="bg-zinc-900 border border-zinc-800 rounded-lg p-4 sm:p-5 space-y-4 font-mono"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="impact-heading" className="text-sm uppercase tracking-wider text-zinc-100 font-bold flex items-center gap-2">
          <Gauge className="w-4 h-4 text-amber-500" />
          What ForgeGuard did
        </h2>
        {USE_MOCK && (
          <span className="px-2 py-0.5 rounded bg-sky-950 text-sky-300 border border-sky-500/40 text-[10px] font-bold tracking-wider">
            MOCK DATA
          </span>
        )}
      </div>

      <dl className="grid grid-cols-2 sm:grid-cols-6 gap-3 text-xs">
        <div className="col-span-2 sm:col-span-1">
          <dt className="text-zinc-400">Readings analysed</dt>
          <dd className="text-lg font-black text-zinc-100">{show(totalReadings)}</dd>
        </div>
        <div>
          <dt className="text-zinc-400">Machines</dt>
          <dd className="text-lg font-black text-zinc-100">{show(hasData ? machines.length : null)}</dd>
        </div>
        {LEVELS.map((level) => (
          <div key={level}>
            <dt className="text-zinc-400">{level}</dt>
            <dd className="text-lg font-black text-zinc-100">{show(count(level))}</dd>
          </div>
        ))}
      </dl>

      <div className="p-3 rounded bg-zinc-950/60 border border-zinc-800 space-y-1.5">
        <div className="text-[11px] uppercase tracking-wider text-zinc-400">Inspect first</div>
        {top ? (
          <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-3">
            <div className="flex items-center gap-2">
              <span className="text-base font-bold text-zinc-100">{top.id}</span>
              <PriorityBadge priority={top.priority} size="sm" />
            </div>
            <p className="font-sans text-xs text-zinc-300 flex-1">{top.summary || '-'}</p>
            <Link
              to={`/machines/${encodeURIComponent(top.id)}`}
              className="inline-flex items-center gap-1 px-3 py-1.5 rounded bg-amber-500 hover:bg-amber-400 text-stone-950 font-bold text-xs transition self-start sm:self-auto"
            >
              Inspect <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>
        ) : (
          <p className="text-sm text-zinc-300">-</p>
        )}
      </div>

      <p className="font-sans text-xs text-zinc-300">
        A technician would otherwise scan all {show(totalReadings)} readings by hand.
      </p>
    </section>
  );
};
