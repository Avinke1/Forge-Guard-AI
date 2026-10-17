import React, { useState, useEffect, useCallback } from 'react';
import { Activity, Cpu, Server, WifiOff, Wifi, RefreshCw, AlertCircle, Clock } from 'lucide-react';
import { LlmStatus } from '../types';
import { getLlmStatus, USE_MOCK, isAmd } from '../api';

const show = (v: string | number | null | undefined) => (v === null || v === undefined || v === '' ? '-' : String(v));

export const StatusPage: React.FC = () => {
  const [status, setStatus] = useState<LlmStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    getLlmStatus()
      .then(setStatus)
      .catch((e) => {
        setStatus(null);
        setError(e?.message || 'Could not reach the backend.');
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const amd = !!status && isAmd(status.provider, status.reachable) && status.reachable;

  const rows: { label: string; value: string; icon: React.ElementType }[] = status
    ? [
        { label: 'Provider', value: show(status.provider), icon: Server },
        { label: 'Model', value: show(status.model), icon: Cpu },
        { label: 'Hardware', value: show(status.hardware), icon: Activity },
        { label: 'Last latency', value: status.latency == null ? '-' : `${status.latency} ms`, icon: Clock },
        { label: 'Last error', value: show(status.lastError), icon: AlertCircle },
      ]
    : [];

  return (
    <div className="space-y-8 py-6 max-w-3xl mx-auto font-mono">
      <div className="border-b border-zinc-800 pb-5">
        <span className="text-xs uppercase tracking-widest text-amber-500 font-semibold">AI status</span>
        <div className="flex items-center justify-between flex-wrap gap-3 mt-1">
          <h1 className="text-2xl sm:text-3xl font-bold text-zinc-100">AI explanation service</h1>
          <div className="flex items-center gap-2">
            {amd && (
              <span className="px-2.5 py-1 rounded bg-[#ed1c24] text-white font-bold text-xs tracking-wider uppercase">
                AMD
              </span>
            )}
            <button
              type="button"
              onClick={load}
              disabled={loading}
              className="inline-flex items-center gap-2 px-3 py-1.5 rounded bg-zinc-800 hover:bg-zinc-700 disabled:opacity-50 text-zinc-200 text-xs font-semibold border border-zinc-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-500"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} aria-hidden="true" />
              Check again
            </button>
          </div>
        </div>
        <p className="text-xs sm:text-sm text-zinc-400 font-sans mt-2">
          Every value below comes from the backend (GET /api/llm/status). Nothing on this page is typed in.
        </p>
      </div>

      {USE_MOCK && (
        <div role="status" className="p-4 rounded-xl bg-zinc-900 border border-amber-500/30 flex items-center gap-3 text-amber-300">
          <WifiOff className="w-5 h-5 text-amber-400 shrink-0" aria-hidden="true" />
          <div className="text-xs">
            <span className="font-bold">AI not connected (mock mode)</span>
            <div className="text-zinc-400 font-sans mt-0.5">Set VITE_USE_MOCK=false to use the backend.</div>
          </div>
        </div>
      )}

      <div aria-live="polite">
        {loading ? (
          <div className="p-12 text-center text-zinc-500 space-y-2">
            <RefreshCw className="w-6 h-6 mx-auto animate-spin text-amber-500" aria-hidden="true" />
            <div className="text-xs">Checking the AI service...</div>
          </div>
        ) : error ? (
          <div role="alert" className="p-5 rounded-xl bg-red-950/40 border border-red-500/40 text-red-200 text-xs space-y-1">
            <div className="font-bold text-red-300">Backend not reachable</div>
            <div className="font-sans">{error}</div>
          </div>
        ) : status && !USE_MOCK ? (
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden divide-y divide-zinc-800">
            <div className="p-4 sm:p-5 flex items-center justify-between">
              <div className="flex items-center gap-3">
                {status.reachable ? (
                  <Wifi className="w-5 h-5 text-emerald-400" aria-hidden="true" />
                ) : (
                  <WifiOff className="w-5 h-5 text-zinc-500" aria-hidden="true" />
                )}
                <div>
                  <div className="text-xs text-zinc-400">Reachable</div>
                  <div className={`text-sm font-bold ${status.reachable ? 'text-emerald-400' : 'text-zinc-300'}`}>
                    {status.reachable ? 'Yes' : 'No'}
                  </div>
                </div>
              </div>
            </div>
            {rows.map(({ label, value, icon: Icon }) => (
              <div key={label} className="p-4 sm:p-5 flex items-center gap-3">
                <Icon className="w-5 h-5 text-zinc-500 shrink-0" aria-hidden="true" />
                <div className="min-w-0">
                  <div className="text-xs text-zinc-400">{label}</div>
                  <div className="text-sm font-bold text-zinc-100 break-words">{value}</div>
                </div>
              </div>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  );
};
