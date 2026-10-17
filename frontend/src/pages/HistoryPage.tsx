import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { History, Clock, FileCheck, Layers, ArrowRight, RefreshCw, CheckCircle2 } from 'lucide-react';
import { RunHistoryItem } from '../types';
import { getRuns, openRun } from '../api';

export const HistoryPage: React.FC = () => {
  const navigate = useNavigate();
  const [runs, setRuns] = useState<RunHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    getRuns()
      .then((data) => {
        if (isMounted) {
          setRuns(data);
          setLoading(false);
        }
      })
      .catch((e) => {
        if (isMounted) {
          setError(e?.message || 'Could not load run history.');
          setLoading(false);
        }
      });
    return () => {
      isMounted = false;
    };
  }, []);

  const handleOpenRun = async (runId: string) => {
    const item = runs.find((r) => r.id === runId);
    if (!item) return;
    try {
      await openRun(item);
      navigate('/queue');
    } catch (e: any) {
      setError(e?.message || 'Could not open this run.');
    }
  };

  const countsText = (run: RunHistoryItem) =>
    run.counts
      ? `HIGH ${run.counts.HIGH ?? 0} · MEDIUM ${run.counts.MEDIUM ?? 0} · LOW ${run.counts.LOW ?? 0} · OK ${run.counts.OK ?? 0}`
      : '-';

  return (
    <div className="space-y-8 py-6">
      {/* Header */}
      <div className="border-b border-zinc-800 pb-5">
        <div className="flex items-center gap-2">
          <span className="font-mono text-xs uppercase tracking-widest text-amber-500 font-semibold">
            Run Logs & Audit Trail
          </span>
        </div>
        <h1 className="text-2xl sm:text-3xl font-bold font-mono text-zinc-100 mt-1">
          Historical Pipeline Runs
        </h1>
        <p className="text-xs sm:text-sm text-zinc-400 font-sans mt-2">
          Past analysis runs saved by the backend. Open one to see its inspection queue again.
        </p>
      </div>

      {error && (
        <div role="alert" className="p-4 rounded-lg bg-red-950/40 border border-red-500/40 text-red-200 font-mono text-xs">
          {error}
        </div>
      )}

      {/* Runs List (Desktop Table) */}
      <div className="hidden md:block bg-zinc-900 border border-zinc-800 rounded-lg overflow-hidden shadow-xl">
        <table className="w-full text-left font-mono text-xs">
          <thead className="bg-zinc-950/90 text-zinc-400 uppercase tracking-wider text-[11px] border-b border-zinc-800">
            <tr>
              <th scope="col" className="px-4 py-3.5">
                Run ID & Batch Name
              </th>
              <th scope="col" className="px-4 py-3.5 w-40">
                Timestamp
              </th>
              <th scope="col" className="px-4 py-3.5">
                Dataset Reference
              </th>
              <th scope="col" className="px-4 py-3.5 w-28 text-center">
                Machines
              </th>
              <th scope="col" className="px-4 py-3.5 w-36">
                Result
              </th>
              <th scope="col" className="px-4 py-3.5 w-28">
                Status
              </th>
              <th scope="col" className="px-4 py-3.5 w-24 text-right">
                Action
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800/80">
            {loading ? (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-zinc-500">
                  <div className="flex items-center justify-center gap-2">
                    <RefreshCw className="w-4 h-4 animate-spin text-amber-500" />
                    <span>Loading past runs...</span>
                  </div>
                </td>
              </tr>
            ) : runs.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-zinc-500">
                  No historical runs recorded.
                </td>
              </tr>
            ) : (
              runs.map((run) => (
                <tr key={run.id} className="hover:bg-zinc-800/50 transition-colors">
                  <td className="px-4 py-4">
                    <div className="font-bold text-zinc-100">{run.name}</div>
                    <div className="text-[10px] text-zinc-500">{run.id}</div>
                  </td>
                  <td className="px-4 py-4 text-zinc-300">
                    <div className="flex items-center gap-1.5 text-zinc-400">
                      <Clock className="w-3.5 h-3.5 text-zinc-500" />
                      <span>{run.timestamp}</span>
                    </div>
                  </td>
                  <td className="px-4 py-4 text-zinc-300 font-sans">{run.dataset}</td>
                  <td className="px-4 py-4 text-center font-bold text-amber-400">
                    {run.machineCount}
                  </td>
                  <td className="px-4 py-4 text-[11px]">
                    <div className="text-zinc-200">{countsText(run)}</div>
                  </td>
                  <td className="px-4 py-4">
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-emerald-950/70 border border-emerald-500/30 text-emerald-300 text-[10px] font-bold">
                      <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                      {run.status}
                    </span>
                  </td>
                  <td className="px-4 py-4 text-right">
                    <button
                      type="button"
                      onClick={() => handleOpenRun(run.id)}
                      className="inline-flex items-center gap-1 px-3 py-1.5 rounded bg-amber-500 hover:bg-amber-400 text-stone-950 font-bold text-xs transition shadow-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-500"
                    >
                      <span>Open</span>
                      <ArrowRight className="w-3.5 h-3.5" />
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Runs Mobile Cards */}
      <div className="block md:hidden space-y-3 font-mono text-xs">
        {loading ? (
          <div className="p-6 text-center text-zinc-500">Loading historical runs...</div>
        ) : (
          runs.map((run) => (
            <div
              key={run.id}
              className="bg-zinc-900 border border-zinc-800 rounded-lg p-4 space-y-3 shadow-md"
            >
              <div className="flex items-center justify-between">
                <span className="font-bold text-zinc-100 text-sm">{run.name}</span>
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-emerald-950 border border-emerald-500/30 text-emerald-400 text-[10px] font-bold">
                  {run.status}
                </span>
              </div>

              <div className="text-zinc-400 text-[11px] space-y-1">
                <div>ID: {run.id}</div>
                <div className="flex items-center gap-1">
                  <Clock className="w-3.5 h-3.5 text-zinc-500" />
                  <span>{run.timestamp}</span>
                </div>
                <div className="text-zinc-300 font-sans">{run.dataset}</div>
              </div>

              <div className="grid grid-cols-2 gap-2 p-2 bg-zinc-950 rounded border border-zinc-800 text-[11px]">
                <div>
                  <span className="text-zinc-500">Machines:</span>{' '}
                  <strong className="text-amber-400">{run.machineCount}</strong>
                </div>
                <div>
                  <span className="text-zinc-500">Result:</span>{' '}
                  <strong className="text-zinc-200">{countsText(run)}</strong>
                </div>
              </div>

              <button
                type="button"
                onClick={() => handleOpenRun(run.id)}
                className="w-full py-2 px-3 rounded bg-amber-500 hover:bg-amber-400 text-stone-950 font-bold text-xs transition flex items-center justify-center gap-1.5 shadow"
              >
                <span>Open Run in Queue</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
