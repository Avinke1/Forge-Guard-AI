import React, { useState, useEffect, useRef } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  Activity,
  Layers,
  ArrowRight,
  Filter,
  AlertTriangle,
  FileText,
  Clock,
  Gauge,
  CheckCircle2,
  Search,
  Mic,
  Square,
  X,
} from 'lucide-react';
import { Machine, PriorityLevel } from '../types';
import { getMachines, getCurrentRun } from '../api';
import { PriorityBadge } from '../components/PriorityBadge';
import { isVoiceSupported, matchSpokenMachine, startVoiceInput } from '../lib/speech';

export const QueuePage: React.FC = () => {
  const [machines, setMachines] = useState<Machine[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<'All' | PriorityLevel>('All');
  const [query, setQuery] = useState('');
  const [error, setError] = useState<string | null>(null);
  const run = getCurrentRun();
  const navigate = useNavigate();
  const [voiceSupported] = useState(isVoiceSupported);
  const [listening, setListening] = useState(false);
  const [voiceError, setVoiceError] = useState<string | null>(null);
  const stopVoice = useRef<(() => void) | null>(null);

  useEffect(() => {
    return () => {
      stopVoice.current?.();
    };
  }, []);

  const toggleVoice = () => {
    if (listening) {
      stopVoice.current?.();
      stopVoice.current = null;
      setListening(false);
      return;
    }

    setVoiceError(null);
    try {
      stopVoice.current = startVoiceInput(
        (transcript) => {
          const machine = matchSpokenMachine(
            transcript,
            machines.map((m) => m.id)
          );
          if (machine) {
            navigate(`/machines/${encodeURIComponent(machine)}`);
          } else {
            setQuery(transcript);
          }
        },
        (message) => setVoiceError(message),
        () => {
          setListening(false);
          stopVoice.current = null;
        }
      );
      setListening(true);
    } catch {
      setListening(false);
      setVoiceError('Unable to start voice recognition.');
    }
  };

  useEffect(() => {
    let isMounted = true;
    getMachines()
      .then((data) => {
        if (isMounted) {
          setMachines(data);
          setLoading(false);
        }
      })
      .catch((e) => {
        if (isMounted) {
          setError(e?.message || 'Could not load the queue.');
          setLoading(false);
        }
      });
    return () => {
      isMounted = false;
    };
  }, []);

  // Search as you type: machine ID, priority or sensor (key or label). Combined with the priority tabs.
  const q = query.trim().toLowerCase();
  const matchesQuery = (m: Machine) => {
    if (!q) return true;
    const sensorWords = [
      ...(m.sensorsInvolved || []),
      ...m.anomalies.flatMap((a) => [a.sensor, a.sensorLabel]),
    ];
    return [m.id, m.priority, ...sensorWords].some((w) => String(w || '').toLowerCase().includes(q));
  };
  const filteredMachines = machines.filter(
    (m) => (filter === 'All' || m.priority === filter) && matchesQuery(m)
  );

  // Calculate metrics
  const totalCount = machines.length;
  const highCount = machines.filter((m) => m.priority === 'HIGH').length;
  const medCount = machines.filter((m) => m.priority === 'MEDIUM').length;
  const lowCount = machines.filter((m) => m.priority === 'LOW').length;
  const okCount = machines.filter((m) => m.priority === 'OK').length;

  return (
    <div className="space-y-8 py-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-zinc-800 pb-5">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs uppercase tracking-widest text-amber-500 font-semibold">
              Live Fleet Triage
            </span>
            <span className="inline-flex items-center px-1.5 py-0.5 rounded bg-zinc-800 text-[10px] font-mono text-zinc-300">
              {run ? `${run.datasetName}${run.real ? ' - Real data: MetroPT-3 (UCI, CC BY 4.0)' : ' - SYNTHETIC'}` : 'No run yet'}
            </span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold font-mono text-zinc-100 tracking-tight mt-1">
            Machine Inspection Queue
          </h1>
        </div>
        <div className="flex items-center gap-2 text-xs font-mono text-zinc-400">
          <Clock className="w-4 h-4 text-amber-500" />
          <span>Run: {run ? run.runId : '-'}</span>
        </div>
      </div>

      {!loading && (error || machines.length === 0) && (
        <div role="status" className="p-6 rounded-xl bg-zinc-900 border border-zinc-800 text-center space-y-3 font-mono">
          <p className="text-sm text-zinc-200 font-bold">{error ? 'Could not load the queue' : 'No analysis yet'}</p>
          <p className="text-xs text-zinc-400 font-sans">{error || 'Run a demo or upload readings to build the inspection queue.'}</p>
          <Link to="/upload" className="inline-flex items-center gap-2 px-4 py-2 rounded bg-amber-500 hover:bg-amber-400 text-stone-950 text-xs font-bold">
            Go to Upload <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      )}

      {!loading && machines.length > 0 && (
        <p className="p-3 rounded-lg bg-zinc-900 border border-zinc-800 font-mono text-xs text-zinc-300">
          This run checked <strong className="text-zinc-100">{machines.reduce((n, m) => n + m.readingsCount, 0).toLocaleString()}</strong>{' '}
          readings from <strong className="text-zinc-100">{totalCount}</strong> machines.{' '}
          <strong className="text-amber-400">{highCount + medCount}</strong> machine{highCount + medCount === 1 ? '' : 's'} need inspection first;{' '}
          {okCount} need no action. Every reason links to its evidence.
        </p>
      )}

      {/* Metric Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4">
        <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-3 sm:p-4">
          <div className="flex items-center justify-between text-zinc-400 text-xs font-mono">
            <span>Fleet Units</span>
            <Layers className="w-4 h-4 text-zinc-500" />
          </div>
          <div className="text-2xl sm:text-3xl font-black font-mono text-zinc-100 mt-2">
            {totalCount}
          </div>
          <div className="text-[11px] font-mono text-zinc-400 mt-1">in this analysis</div>
        </div>

        <div className="bg-red-950/20 border border-red-500/30 rounded-lg p-3 sm:p-4">
          <div className="flex items-center justify-between text-red-400 text-xs font-mono">
            <span>High Priority</span>
            <AlertTriangle className="w-4 h-4 text-red-400" />
          </div>
          <div className="text-2xl sm:text-3xl font-black font-mono text-red-400 mt-2">
            {highCount}
          </div>
          <div className="text-[11px] font-mono text-red-300/80 mt-1">Require immediate inspection</div>
        </div>

        <div className="bg-amber-950/20 border border-amber-500/30 rounded-lg p-3 sm:p-4">
          <div className="flex items-center justify-between text-amber-400 text-xs font-mono">
            <span>Med / Low</span>
            <Activity className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-2xl sm:text-3xl font-black font-mono text-amber-400 mt-2">
            {medCount + lowCount}
          </div>
          <div className="text-[11px] font-mono text-amber-300/80 mt-1">
            {medCount} Medium, {lowCount} Data Flags
          </div>
        </div>

        <div className="bg-emerald-950/20 border border-emerald-500/30 rounded-lg p-3 sm:p-4">
          <div className="flex items-center justify-between text-emerald-400 text-xs font-mono">
            <span>Normal / OK</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-2xl sm:text-3xl font-black font-mono text-emerald-400 mt-2">
            {okCount}
          </div>
          <div className="text-[11px] font-mono text-emerald-300/80 mt-1">Within standard limits</div>
        </div>
      </div>

      {/* Search */}
      <div className="relative max-w-md">
        <label htmlFor="queue-search" className="sr-only">
          Search machines by ID, priority or sensor
        </label>
        <Search className="w-4 h-4 text-zinc-500 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
        <input
          id="queue-search"
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search machine ID, priority or sensor (e.g. HP-01, HIGH, vibration)"
          autoComplete="off"
          className="w-full pl-9 pr-20 py-2 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-100 placeholder:text-zinc-500 font-mono text-xs focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-500"
        />
        {query && (
          <button
            type="button"
            onClick={() => setQuery('')}
            aria-label="Clear search"
            className="absolute right-10 top-1/2 -translate-y-1/2 p-1 rounded text-zinc-400 hover:text-zinc-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-500"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        )}
        {voiceSupported && (
          <button
            type="button"
            onClick={toggleVoice}
            disabled={loading}
            aria-label={listening ? 'Stop voice search' : 'Search by voice'}
            aria-pressed={listening}
            title={listening ? 'Stop listening' : 'Voice search (Chrome/Edge)'}
            className={`absolute right-2 top-1/2 -translate-y-1/2 p-1 rounded focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-500 ${
              listening ? 'text-red-400' : 'text-amber-400 hover:text-amber-300'
            }`}
          >
            {listening ? <Square className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
          </button>
        )}
      </div>
      {!voiceSupported && (
        <p className="text-xs text-zinc-400">Voice works in Chrome/Edge</p>
      )}
      {voiceError && (
        <p role="alert" className="text-xs text-red-400">{voiceError}</p>
      )}

      {/* Filter Tabs */}
      <div className="flex flex-wrap items-center gap-2 border-b border-zinc-800 pb-3">
        <div className="flex items-center gap-1 text-zinc-400 font-mono text-xs mr-2">
          <Filter className="w-3.5 h-3.5" />
          <span>Filter:</span>
        </div>
        {(['All', 'HIGH', 'MEDIUM', 'LOW', 'OK'] as const).map((level) => {
          const isSelected = filter === level;
          const count =
            level === 'All'
              ? totalCount
              : machines.filter((m) => m.priority === level).length;
          return (
            <button
              key={level}
              type="button"
              onClick={() => setFilter(level)}
              className={`px-3 py-1.5 rounded text-xs font-mono font-medium transition focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-500 ${
                isSelected
                  ? 'bg-amber-500 text-stone-950 font-bold shadow'
                  : 'bg-zinc-900 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 border border-zinc-800'
              }`}
            >
              {level} <span className="opacity-80">({count})</span>
            </button>
          );
        })}
      </div>

      {/* Ranked Table (Desktop) */}
      <div className="hidden md:block bg-zinc-900 border border-zinc-800 rounded-lg overflow-hidden shadow-xl">
        <table className="w-full text-left font-mono text-xs">
          <thead className="bg-zinc-950/90 text-zinc-400 uppercase tracking-wider text-[11px] border-b border-zinc-800">
            <tr>
              <th scope="col" className="px-4 py-3.5 w-14 text-center">
                Rank
              </th>
              <th scope="col" className="px-4 py-3.5 w-32">
                Priority
              </th>
              <th scope="col" className="px-4 py-3.5 w-36">
                Machine ID
              </th>
              <th scope="col" className="px-4 py-3.5">
                Summary & Trigger
              </th>
              <th scope="col" className="px-4 py-3.5 w-36">
                Anomalies / Flags
              </th>
              <th scope="col" className="px-4 py-3.5 w-32">
                Notes
              </th>
              <th scope="col" className="px-4 py-3.5 w-28 text-right">
                Action
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800/80">
            {loading ? (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-zinc-500">
                  Loading fleet queue...
                </td>
              </tr>
            ) : filteredMachines.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-zinc-500">
                  No machines match
                </td>
              </tr>
            ) : (
              filteredMachines.map((m) => (
                <tr
                  key={m.id}
                  className="hover:bg-zinc-800/50 transition-colors group"
                >
                  <td className="px-4 py-4 text-center font-bold text-amber-500 text-sm">
                    #{m.rank}
                  </td>
                  <td className="px-4 py-4">
                    <PriorityBadge priority={m.priority} size="sm" />
                  </td>
                  <td className="px-4 py-4">
                    <div className="font-bold text-zinc-100 text-sm">{m.id}</div>
                    <div className="text-[10px] text-zinc-400 truncate">{m.name}</div>
                  </td>
                  <td className="px-4 py-4 text-zinc-300 font-sans text-xs">
                    <div className="font-medium text-zinc-200">{m.summary}</div>
                    <div className="text-[11px] text-zinc-400 mt-0.5">{m.location}</div>
                  </td>
                  <td className="px-4 py-4">
                    {m.anomalies.length > 0 ? (
                      <div className="flex flex-wrap gap-1">
                        {m.anomalies.map((a) => (
                          <span
                            key={a.id}
                            className="px-1.5 py-0.5 rounded bg-red-950/80 text-red-300 text-[10px] font-bold border border-red-500/40"
                          >
                            {a.id} ({a.sensorLabel})
                          </span>
                        ))}
                      </div>
                    ) : m.warnings.length > 0 ? (
                      <div className="flex flex-col gap-0.5 text-[10px] text-sky-300">
                        {m.warnings.slice(0, 2).map((w, idx) => (
                          <span key={idx} className="truncate">
                            ⚠ {w}
                          </span>
                        ))}
                      </div>
                    ) : (
                      <span className="text-emerald-400 text-[11px]">Normal</span>
                    )}
                  </td>
                  <td className="px-4 py-4">
                    {m.notes.length > 0 ? (
                      <div className="flex flex-wrap gap-1">
                        {m.notes.map((n) => (
                          <span
                            key={n.id}
                            className="px-1.5 py-0.5 rounded bg-blue-950/70 text-blue-300 text-[10px] border border-blue-500/30"
                          >
                            {n.id}
                          </span>
                        ))}
                      </div>
                    ) : (
                      <span className="text-zinc-500 text-[11px]">None</span>
                    )}
                  </td>
                  <td className="px-4 py-4 text-right">
                    <Link
                      to={`/machines/${m.id}`}
                      className="inline-flex items-center gap-1 px-3 py-1.5 rounded bg-amber-500 hover:bg-amber-400 text-stone-950 font-bold text-xs transition shadow-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-500"
                    >
                      <span>Inspect</span>
                      <ArrowRight className="w-3.5 h-3.5" />
                    </Link>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Responsive Cards (Mobile / 390px Viewport) */}
      <div className="block md:hidden space-y-3 font-mono">
        {loading ? (
          <div className="p-6 text-center text-zinc-500 text-xs">Loading queue...</div>
        ) : filteredMachines.length === 0 ? (
          <div className="p-6 text-center text-zinc-500 text-xs">
            No machines match
          </div>
        ) : (
          filteredMachines.map((m) => (
            <div
              key={m.id}
              className="bg-zinc-900 border border-zinc-800 rounded-lg p-4 space-y-3 shadow-md"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-amber-500 font-bold text-sm">#{m.rank}</span>
                  <span className="font-bold text-base text-zinc-100">{m.id}</span>
                </div>
                <PriorityBadge priority={m.priority} size="sm" />
              </div>

              <div className="text-xs font-sans text-zinc-300">
                <div className="font-semibold text-zinc-200">{m.summary}</div>
                <div className="text-[11px] text-zinc-400 mt-0.5">{m.name} • {m.location}</div>
              </div>

              {/* Badges / Details */}
              <div className="flex flex-wrap gap-1.5 text-[10px] pt-1">
                {m.anomalies.map((a) => (
                  <span
                    key={a.id}
                    className="px-1.5 py-0.5 rounded bg-red-950 text-red-300 border border-red-500/40"
                  >
                    Anomaly {a.id}
                  </span>
                ))}
                {m.notes.map((n) => (
                  <span
                    key={n.id}
                    className="px-1.5 py-0.5 rounded bg-blue-950 text-blue-300 border border-blue-500/30"
                  >
                    Note {n.id}
                  </span>
                ))}
                {m.warnings.map((w, idx) => (
                  <span
                    key={idx}
                    className="px-1.5 py-0.5 rounded bg-sky-950 text-sky-300 border border-sky-500/30"
                  >
                    {w}
                  </span>
                ))}
              </div>

              <div className="pt-2 border-t border-zinc-800 flex justify-end">
                <Link
                  to={`/machines/${m.id}`}
                  className="w-full text-center py-2 px-3 rounded bg-amber-500 hover:bg-amber-400 text-stone-950 font-bold text-xs transition flex items-center justify-center gap-1.5 shadow"
                >
                  <span>Inspect Machine</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </Link>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
