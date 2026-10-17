import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  FileCheck2,
  Activity,
  FileText,
  ListOrdered,
  Cpu,
  ShieldCheck,
  ArrowRight,
  Database,
  Layers,
  Play,
  ChevronRight,
  AlertCircle,
} from 'lucide-react';
import { runDemo, DatasetId } from '../api';

const pipelineSteps = [
  {
    num: '01',
    title: 'Validate data',
    description: 'Check columns, timestamps and values. Impossible values and empty cells are reported, rows that cannot be used are dropped and counted.',
    icon: FileCheck2,
  },
  {
    num: '02',
    title: 'Detect unusual readings',
    description: "Limit rules plus each machine's own normal pattern. A one-reading spike is ignored - an alert must last at least 2 readings.",
    icon: Activity,
  },
  {
    num: '03',
    title: 'Match maintenance notes',
    description: 'Technician notes written before, during and after an unusual period are linked to it.',
    icon: FileText,
  },
  {
    num: '04',
    title: 'Rank',
    description: 'Every machine gets HIGH, MEDIUM, LOW or OK, so the technician knows which one to inspect first.',
    icon: ListOrdered,
  },
  {
    num: '05',
    title: 'Explain with AI on AMD',
    description: 'An open AI model running on AMD hardware writes the explanation through our backend: findings, possible causes, checks and uncertainty. The model and provider are shown on every report.',
    icon: Cpu,
    highlight: true,
  },
  {
    num: '06',
    title: 'Verify evidence',
    description: 'Every evidence ID the AI cites must exist in the analysis. Claims without real evidence are marked "Unsupported".',
    icon: ShieldCheck,
  },
];

const flow = ['CSV readings + notes', 'Detect', 'Match notes', 'Rank', 'AI explanation on AMD', 'Verify evidence', 'Inspection queue'];

export const OverviewPage: React.FC = () => {
  const navigate = useNavigate();
  const [busy, setBusy] = useState<DatasetId | null>(null);
  const [error, setError] = useState<string | null>(null);

  const startDemo = async (id: DatasetId) => {
    setBusy(id);
    setError(null);
    try {
      await runDemo(id);
      navigate('/queue');
    } catch (e: any) {
      setError(e?.message || 'Demo could not be started.');
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="space-y-12 py-6">
      {/* Hero */}
      <section className="relative overflow-hidden rounded-xl bg-gradient-to-b from-zinc-900 to-zinc-950 border border-zinc-800 p-6 sm:p-10 lg:p-12 shadow-2xl">
        <div className="absolute top-0 right-0 -mt-10 -mr-10 w-80 h-80 bg-amber-500/5 rounded-full blur-3xl pointer-events-none" />
        <div className="max-w-3xl space-y-5">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-amber-500/10 border border-amber-500/30 text-amber-400 font-mono text-xs tracking-wider">
            MAINTENANCE DECISION SUPPORT
          </div>

          <h1 className="text-3xl sm:text-5xl font-black font-mono tracking-tight text-white leading-tight">
            Turn machine signals into an inspection plan.
          </h1>

          <p className="text-zinc-300 text-sm sm:text-base leading-relaxed max-w-2xl font-sans">
            Technicians see which machine to inspect first and why - with proof. ForgeGuard ranks the machines,
            links every reason to the exact readings and notes, and suggests what to check.
            A qualified technician makes the decision.
          </p>

          <div className="pt-2 flex flex-wrap gap-4 font-mono text-xs sm:text-sm">
            <button
              type="button"
              onClick={() => startDemo('synthetic_fleet')}
              disabled={busy !== null}
              className="inline-flex items-center gap-2 px-6 py-3.5 rounded-lg bg-amber-500 hover:bg-amber-400 disabled:opacity-60 text-stone-950 font-bold transition shadow-lg shadow-amber-500/20 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-300"
            >
              {busy === 'synthetic_fleet' ? (
                <span className="w-4 h-4 border-2 border-stone-950 border-t-transparent rounded-full animate-spin" />
              ) : (
                <Play className="w-4 h-4 fill-stone-950" />
              )}
              <span>{busy === 'synthetic_fleet' ? 'Running demo...' : 'Try the demo'}</span>
            </button>
            <Link
              to="/upload"
              className="inline-flex items-center gap-2 px-5 py-3.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-100 font-semibold border border-zinc-700 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-500"
            >
              <span>Upload your own CSV</span>
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
          {error && (
            <p role="alert" className="flex items-center gap-2 text-xs font-mono text-red-300">
              <AlertCircle className="w-4 h-4" /> {error}
            </p>
          )}
        </div>
      </section>

      {/* Pipeline diagram */}
      <section aria-labelledby="flow-heading" className="space-y-4">
        <div className="border-b border-zinc-800 pb-3">
          <span className="font-mono text-xs uppercase tracking-widest text-amber-500">How it works</span>
          <h2 id="flow-heading" className="text-xl sm:text-2xl font-bold font-mono text-zinc-100">
            From raw readings to a verified inspection queue
          </h2>
        </div>
        <ol className="flex flex-col lg:flex-row lg:flex-wrap items-stretch gap-2 font-mono text-xs">
          {flow.map((label, i) => {
            const amd = label.includes('AMD');
            return (
              <li key={label} className="flex flex-col lg:flex-row items-center gap-2">
                <div
                  className={`w-full lg:w-auto px-3 py-2.5 rounded-lg border text-center font-semibold ${
                    amd
                      ? 'border-[#ed1c24]/60 bg-[#ed1c24]/10 text-red-200'
                      : 'border-zinc-700 bg-zinc-900 text-zinc-200'
                  }`}
                >
                  {label}
                </div>
                {i < flow.length - 1 && (
                  <ChevronRight aria-hidden="true" className="w-4 h-4 text-zinc-500 rotate-90 lg:rotate-0 shrink-0" />
                )}
              </li>
            );
          })}
        </ol>
      </section>

      {/* 6 steps */}
      <section className="space-y-6">
        <div className="border-b border-zinc-800 pb-4">
          <span className="font-mono text-xs uppercase tracking-widest text-amber-500">The pipeline</span>
          <h2 className="text-xl sm:text-2xl font-bold font-mono text-zinc-100">6 steps, every one traceable</h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {pipelineSteps.map((step) => {
            const Icon = step.icon;
            return (
              <div
                key={step.num}
                className={`rounded-lg p-5 border space-y-3 transition ${
                  step.highlight
                    ? 'bg-zinc-900/90 border-amber-500/40 shadow-lg shadow-amber-500/5'
                    : 'bg-zinc-900/40 border-zinc-800 hover:border-zinc-700'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono text-2xl font-black text-amber-500/80">{step.num}</span>
                  <div
                    className={`p-2 rounded ${
                      step.highlight ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30' : 'bg-zinc-800 text-zinc-300'
                    }`}
                  >
                    <Icon className="w-5 h-5" aria-hidden="true" />
                  </div>
                </div>
                <h3 className="font-mono font-bold text-base text-zinc-100 leading-snug">{step.title}</h3>
                <p className="text-xs text-zinc-400 leading-relaxed font-sans">{step.description}</p>
              </div>
            );
          })}
        </div>
      </section>

      {/* Datasets */}
      <section className="space-y-6">
        <div className="border-b border-zinc-800 pb-4">
          <span className="font-mono text-xs uppercase tracking-widest text-amber-500">Demo data</span>
          <h2 className="text-xl sm:text-2xl font-bold font-mono text-zinc-100">Two datasets to try</h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-6 flex flex-col justify-between gap-5">
            <div className="space-y-3">
              <span className="inline-block px-2.5 py-1 rounded bg-amber-500/10 text-amber-400 text-xs font-mono font-semibold border border-amber-500/20">
                SYNTHETIC
              </span>
              <h3 className="text-lg font-bold font-mono text-zinc-100 flex items-center gap-2">
                <Layers className="w-5 h-5 text-amber-500" aria-hidden="true" />
                Synthetic fleet
              </h3>
              <p className="text-xs text-zinc-400 leading-relaxed font-sans">
                6 machines (hydraulic presses, forming presses, drive shafts), readings every 15 minutes, 14-16 Oct 2026,
                with 20 technician notes. Includes planted cases: bearing wear, overheating, overpressure, a one-off spike
                that must be ignored, and messy data.
              </p>
            </div>
            <button
              type="button"
              onClick={() => startDemo('synthetic_fleet')}
              disabled={busy !== null}
              className="w-full py-2.5 px-4 rounded-lg bg-amber-500 hover:bg-amber-400 disabled:opacity-60 text-stone-950 font-mono text-xs font-bold transition flex items-center justify-center gap-2"
            >
              <Play className="w-4 h-4" aria-hidden="true" />
              <span>{busy === 'synthetic_fleet' ? 'Running...' : 'Run synthetic fleet demo'}</span>
            </button>
          </div>

          <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-6 flex flex-col justify-between gap-5">
            <div className="space-y-3">
              <span className="inline-block px-2.5 py-1 rounded bg-blue-500/10 text-blue-300 text-xs font-mono font-semibold border border-blue-500/20">
                Real data: MetroPT-3 (UCI, CC BY 4.0)
              </span>
              <h3 className="text-lg font-bold font-mono text-zinc-100 flex items-center gap-2">
                <Database className="w-5 h-5 text-blue-400" aria-hidden="true" />
                MetroPT-3
              </h3>
              <p className="text-xs text-zinc-400 leading-relaxed font-sans">
                Real sensor data from one metro train air compressor (APU-01) in Porto, with real maintenance records.
                The demo window (8-16 Jul 2020) contains a recorded air-leak failure. These sensors have no fixed limits,
                so each reading is compared with the machine's own normal pattern.
              </p>
            </div>
            <button
              type="button"
              onClick={() => startDemo('metropt3')}
              disabled={busy !== null}
              className="w-full py-2.5 px-4 rounded-lg bg-zinc-800 hover:bg-zinc-700 disabled:opacity-60 text-zinc-100 font-mono text-xs font-semibold border border-zinc-700 transition flex items-center justify-center gap-2"
            >
              <Play className="w-4 h-4" aria-hidden="true" />
              <span>{busy === 'metropt3' ? 'Running...' : 'Run MetroPT-3 demo (real data)'}</span>
            </button>
          </div>
        </div>
      </section>
    </div>
  );
};
