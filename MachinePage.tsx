import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  ArrowLeft,
  Sparkles,
  AlertTriangle,
  FileText,
  AlertCircle,
  HelpCircle,
  CheckCircle,
  Clock,
  MapPin,
  RefreshCw,
  ExternalLink,
  Cpu,
  ShieldCheck,
} from 'lucide-react';
import { Machine, SensorReading, MachineReport, EvidenceDetail, SensorConfig } from '../types';
import {
  getMachineById,
  getMachineReadings,
  explainMachine,
  getEvidenceDetail,
  getSensors,
  isAmd,
} from '../api';
import { PriorityBadge } from '../components/PriorityBadge';
import { SensorChart } from '../components/SensorChart';
import { EvidenceDrawer } from '../components/EvidenceDrawer';

export const MachinePage: React.FC = () => {
  const { id } = useParams<{ id: string }>();

  const [machine, setMachine] = useState<Machine | null>(null);
  const [readings, setReadings] = useState<SensorReading[]>([]);
  const [report, setReport] = useState<MachineReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [reportLoading, setReportLoading] = useState(false);
  const [reportError, setReportError] = useState<string | null>(null);
  const [sensors, setSensors] = useState<SensorConfig[]>([]);
  const [notFound, setNotFound] = useState(false);

  // Evidence drawer state
  const [selectedEvidence, setSelectedEvidence] = useState<EvidenceDetail | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    setNotFound(false);
    setReport(null);
    setReportError(null);

    Promise.all([getMachineById(id), getMachineReadings(id), getSensors()])
      .then(([machineData, readingsData, sensorData]) => {
        if (!machineData) {
          setNotFound(true);
          setLoading(false);
          return;
        }
        setMachine(machineData);
        setReadings(readingsData);
        setSensors(sensorData);
        setLoading(false);
      })
      .catch(() => {
        setNotFound(true);
        setLoading(false);
      });
  }, [id]);

  const handleGenerateReport = async () => {
    if (!id) return;
    setReportLoading(true);
    setReportError(null);
    try {
      const generated = await explainMachine(id);
      setReport(generated);
    } catch (e: any) {
      setReportError(e?.message || 'AI explanation request failed.');
    } finally {
      setReportLoading(false);
    }
  };

  const handleChipClick = async (evidenceId: string) => {
    if (!machine) return;
    const detail = await getEvidenceDetail(machine.id, evidenceId);
    setSelectedEvidence(detail);
    setDrawerOpen(true);
  };

  // IDs that exist in this analysis (used to mark unsupported citations - lookup only)
  const knownIds = new Set<string>([
    ...(machine?.anomalies.map((a) => a.id) || []),
    ...(machine?.notes.map((n) => n.id) || []),
    ...readings.map((r) => r.id),
  ]);
  const isUnknownId = (eid: string) => !knownIds.has(eid);
  // Verified = at least one cited ID AND every cited ID exists in this analysis
  const findingUnsupported = (f: { unsupported?: boolean; evidence: string[] }) =>
    !!f.unsupported || f.evidence.length === 0 || f.evidence.some(isUnknownId);
  const supportedCount = report ? report.findings.filter((f) => !findingUnsupported(f)).length : 0;

  if (loading) {
    return (
      <div className="py-20 text-center font-mono text-zinc-400 space-y-3">
        <RefreshCw className="w-8 h-8 mx-auto animate-spin text-amber-500" />
        <p>Loading machine telemetry stream...</p>
      </div>
    );
  }

  if (notFound || !machine) {
    return (
      <div className="py-16 text-center space-y-4 font-mono">
        <div className="inline-flex p-3 rounded-full bg-red-950/60 border border-red-500/30 text-red-400">
          <AlertCircle className="w-8 h-8" />
        </div>
        <h1 className="text-xl sm:text-2xl font-bold text-zinc-100">
          Machine not found in this analysis
        </h1>
        <p className="text-xs text-zinc-400 max-w-md mx-auto font-sans">
          The machine <code className="text-amber-400">{id}</code> is not part of the current analysis run.
        </p>
        <div className="pt-2">
          <Link
            to="/queue"
            className="inline-flex items-center gap-2 px-4 py-2 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-mono font-medium transition"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Return to Inspection Queue</span>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8 py-6">
      {/* Top Breadcrumb & Machine Header */}
      <div className="space-y-4 border-b border-zinc-800 pb-6">
        <Link
          to="/queue"
          className="inline-flex items-center gap-1.5 text-xs font-mono text-zinc-400 hover:text-amber-400 transition"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to Fleet Queue</span>
        </Link>

        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex flex-wrap items-center gap-3">
              <h1 className="text-2xl sm:text-3xl font-black font-mono text-zinc-100">
                {machine.id}
              </h1>
              <span className="text-zinc-500 font-mono">/</span>
              <span className="text-zinc-300 font-mono text-sm sm:text-base font-semibold">
                {machine.name}
              </span>
              <PriorityBadge priority={machine.priority} size="md" />
            </div>

            <div className="flex flex-wrap items-center gap-4 text-xs font-mono text-zinc-400 pt-1">
              <span className="flex items-center gap-1">
                <MapPin className="w-3.5 h-3.5 text-zinc-500" />
                {machine.location}
              </span>
              <span className="flex items-center gap-1">
                <Clock className="w-3.5 h-3.5 text-zinc-500" />
                Latest Reading: {machine.lastReading}
              </span>
              <span className="text-zinc-500">|</span>
              <span className="text-zinc-300">Type: {machine.type}</span>
            </div>
          </div>

          {/* Trigger button for Report */}
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={handleGenerateReport}
              disabled={reportLoading}
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-amber-500 hover:bg-amber-400 disabled:opacity-50 text-stone-950 font-mono text-xs font-bold transition shadow-lg shadow-amber-500/10 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-500"
            >
              {reportLoading ? (
                <RefreshCw className="w-4 h-4 animate-spin" />
              ) : (
                <Sparkles className="w-4 h-4 fill-stone-950/20" />
              )}
              <span>
                {reportLoading
                  ? 'The AI is writing the explanation (up to 60 s)...'
                  : report
                  ? 'Regenerate AI explanation'
                  : 'Generate AI explanation'}
              </span>
            </button>
          </div>
        </div>

        {/* Machine Summary Banner */}
        <div className="p-3.5 rounded bg-zinc-900 border border-zinc-800 flex items-start gap-3">
          <AlertTriangle className="w-4 h-4 text-amber-500 shrink-0 mt-0.5" />
          <div className="font-mono text-xs">
            <span className="text-zinc-400 uppercase tracking-wider mr-2 font-semibold">
              Signal Triage Summary:
            </span>
            <span className="text-zinc-200 font-medium">{machine.summary}</span>
          </div>
        </div>
      </div>

      {reportError && (
        <div role="alert" className="p-4 rounded-lg bg-red-950/50 border border-red-500/50 text-red-200 font-mono text-xs">
          <div className="font-bold text-red-300 flex items-center gap-2">
            <AlertCircle className="w-4 h-4" /> AI explanation failed
          </div>
          <p className="font-sans mt-1">{reportError}</p>
        </div>
      )}

      {/* AI Explanation / Report Section */}
      {report && (
        <section
          aria-labelledby="report-heading"
          className="rounded-xl border border-amber-500/30 bg-zinc-950 p-5 sm:p-6 space-y-6 shadow-2xl"
        >
          {/* Header */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-zinc-800 pb-3">
            <div className="flex items-center gap-2">
              <span className="px-2 py-0.5 rounded bg-amber-500/10 border border-amber-500/30 text-amber-400 font-mono text-xs font-bold uppercase tracking-wider">
                {report.header}
              </span>
              <span className="text-xs font-mono text-zinc-500">Evaluation Report</span>
            </div>
            <span className="text-[11px] font-mono text-zinc-400">Target: {machine.id}</span>
          </div>

          {/* Generated-by line + evidence check (values only from the backend response) */}
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 -mt-2">
            <div className="flex items-center gap-2 font-mono text-xs text-zinc-300 flex-wrap">
              <Cpu className="w-4 h-4 text-zinc-400 shrink-0" />
              {report.mock ? (
                <span>Generated by: mock data (no AI model connected)</span>
              ) : (
                <span>
                  Generated by <strong className="text-zinc-100">{report.model || 'unknown model'}</strong> via{' '}
                  <strong className="text-zinc-100">{report.provider || 'unknown provider'}</strong>
                  {report.hardware ? (
                    <>
                      {' '}on <strong className="text-zinc-100">{report.hardware}</strong>
                    </>
                  ) : null}
                  {report.latencyMs != null ? <> in {(report.latencyMs / 1000).toFixed(1)} s</> : null}
                </span>
              )}
              {!report.mock && isAmd(report.provider) && (
                <span className="px-1.5 py-0.5 rounded bg-[#ed1c24] text-white text-[10px] font-bold tracking-wider">AMD</span>
              )}
            </div>
            {report.findings.length > 0 && (
              <div
                className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded font-mono text-xs font-bold border ${
                  supportedCount === report.findings.length
                    ? 'bg-emerald-950/50 border-emerald-500/40 text-emerald-300'
                    : 'bg-amber-950/40 border-amber-500/40 text-amber-300'
                }`}
              >
                <ShieldCheck className="w-3.5 h-3.5" />
                Evidence check: {supportedCount} of {report.findings.length} findings verified
              </div>
            )}
          </div>

          {/* Failure & Rule-Based Fallback Banner (for FP-02) */}
          {report.failed && (
            <div className="p-4 rounded-lg bg-red-950/50 border border-red-500/50 space-y-2">
              <div className="flex items-center gap-2 text-red-400 font-mono font-bold text-sm">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>AI explanation failed</span>
              </div>
              <p className="text-xs font-sans text-red-200 leading-relaxed">
                {report.errorMessage || 'Inference call timed out or failed to parse.'}
              </p>
              {report.ruleBasedFallback && (
                <div className="mt-1 space-y-1">
                  <div className="inline-block px-2.5 py-1 rounded bg-zinc-900 text-amber-300 border border-amber-500/30 font-mono text-xs font-semibold">
                    Rule-based summary (no AI)
                  </div>
                  {report.ruleBasedSummary && (
                    <p className="text-xs font-sans text-zinc-200 leading-relaxed">{report.ruleBasedSummary}</p>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Report Summary */}
          {report.summary && (
            <div className="space-y-1.5">
              <h3 className="font-mono text-xs uppercase tracking-wider text-zinc-400 font-semibold">
                Summary
              </h3>
              <p className="text-sm text-zinc-200 font-sans leading-relaxed bg-zinc-900/60 p-3.5 rounded border border-zinc-800">
                {report.summary}
              </p>
            </div>
          )}

          {/* Findings with Evidence Chips */}
          <div className="space-y-3">
            <h3 className="font-mono text-xs uppercase tracking-wider text-zinc-400 font-semibold">
              Findings & Traceable Evidence
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {report.findings.map((f) => {
                const isUnsupportedFinding = findingUnsupported(f);
                return (
                  <div
                    key={f.id}
                    className={`rounded-lg p-4 border transition ${
                      isUnsupportedFinding
                        ? 'bg-zinc-900/30 border-zinc-800 text-zinc-500 opacity-75'
                        : 'bg-zinc-900/80 border-zinc-800 text-zinc-200'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2 mb-2">
                      <span className="font-mono font-bold text-sm text-zinc-100 flex items-center gap-1.5">
                        {f.title}
                      </span>
                      {isUnsupportedFinding && (
                        <span className="px-2 py-0.5 rounded bg-zinc-800 text-zinc-400 border border-zinc-700 font-mono text-[10px] font-semibold uppercase tracking-wider">
                          {f.evidence.length === 0 ? 'No evidence cited' : 'Unsupported'}
                        </span>
                      )}
                    </div>
                    <p className="text-xs font-sans text-zinc-300 leading-relaxed mb-3">
                      {f.detail}
                    </p>

                    {/* Evidence Chips */}
                    <div className="pt-2 border-t border-zinc-800 flex flex-wrap items-center gap-2">
                      <span className="text-[10px] font-mono uppercase text-zinc-400">
                        Citations:
                      </span>
                      {f.evidence.length === 0 ? (
                        <span className="text-[10px] font-mono text-zinc-500">None</span>
                      ) : (
                        f.evidence.map((chip) => {
                          const isInvalidChip = isUnknownId(chip);
                          return (
                            <button
                              key={chip}
                              type="button"
                              onClick={() => handleChipClick(chip)}
                              className={`inline-flex items-center gap-1 px-2 py-0.5 rounded font-mono text-xs font-bold transition focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-500 ${
                                isInvalidChip
                                  ? 'bg-zinc-800 text-zinc-400 line-through border border-zinc-700 hover:bg-zinc-700'
                                  : 'bg-amber-500/15 text-amber-400 hover:bg-amber-500/25 border border-amber-500/40 hover:text-amber-300'
                              }`}
                              title={
                                isInvalidChip
                                  ? 'Click to inspect unsupported reference'
                                  : `Click to inspect evidence ${chip}`
                              }
                            >
                              <span>[{chip}]</span>
                              <ExternalLink className="w-2.5 h-2.5 opacity-70" />
                            </button>
                          );
                        })
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Causes & Recommended Checks */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
            <div className="space-y-2 bg-zinc-900/60 p-4 rounded-lg border border-zinc-800">
              <h4 className="font-mono text-xs uppercase tracking-wider text-amber-400 font-semibold flex items-center gap-1.5">
                <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
                Possible Causes
              </h4>
              <ul className="space-y-1.5 font-sans text-xs text-zinc-300 list-disc list-inside">
                {report.possibleCauses.map((c, i) => (
                  <li key={i}>{c}</li>
                ))}
              </ul>
            </div>

            <div className="space-y-2 bg-zinc-900/60 p-4 rounded-lg border border-zinc-800">
              <h4 className="font-mono text-xs uppercase tracking-wider text-emerald-400 font-semibold flex items-center gap-1.5">
                <CheckCircle className="w-3.5 h-3.5 text-emerald-400" />
                Recommended Checks
              </h4>
              <ul className="space-y-1.5 font-sans text-xs text-zinc-300 list-disc list-inside">
                {report.recommendedChecks.map((chk, i) => (
                  <li key={i}>{chk}</li>
                ))}
              </ul>
            </div>
          </div>

          {/* Missing Information & Uncertainty */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-1 font-mono text-xs">
            <div className="p-3.5 rounded bg-zinc-900/40 border border-zinc-800 space-y-1">
              <span className="text-zinc-400 uppercase tracking-wider text-[11px] font-semibold flex items-center gap-1.5">
                <HelpCircle className="w-3.5 h-3.5 text-zinc-400" />
                Missing Information
              </span>
              <p className="text-zinc-300 font-sans text-xs">
                {report.missingInformation.length > 0
                  ? report.missingInformation.join('; ')
                  : 'All operational parameters present in ingest window.'}
              </p>
            </div>

            <div className="p-3.5 rounded bg-zinc-900/40 border border-zinc-800 space-y-1">
              <span className="text-zinc-400 uppercase tracking-wider text-[11px] font-semibold">
                Uncertainty Assessment
              </span>
              <p className="text-zinc-300 font-sans text-xs">{report.uncertainty}</p>
            </div>
          </div>
        </section>
      )}

      {/* Anomalies List */}
      <section className="space-y-3">
        <div className="flex items-center justify-between border-b border-zinc-800 pb-2">
          <h2 className="font-mono text-sm uppercase tracking-wider text-zinc-200 font-bold flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-red-400" />
            Detected Sensor Anomalies ({machine.anomalies.length})
          </h2>
          <span className="text-xs font-mono text-zinc-400">Boundary Violations</span>
        </div>

        {machine.anomalies.length === 0 ? (
          <div className="p-4 rounded bg-zinc-900 border border-zinc-800 text-xs font-mono text-zinc-400">
            No unusual readings flagged for this machine in this analysis.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {machine.anomalies.map((a) => (
              <div
                key={a.id}
                className="bg-zinc-900 border border-zinc-800 rounded-lg p-3.5 space-y-2 hover:border-zinc-700 transition"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => handleChipClick(a.id)}
                      className="px-2 py-0.5 rounded bg-red-950/80 text-red-300 font-mono text-xs font-bold border border-red-500/40 hover:bg-red-900"
                    >
                      [{a.id}]
                    </button>
                    <span className="font-mono text-xs font-semibold text-zinc-200">
                      {a.sensorLabel}
                    </span>
                  </div>
                  <span className="text-[11px] font-mono text-amber-400">{a.timestamp}</span>
                </div>
                <p className="text-xs font-sans text-zinc-300">{a.description}</p>
                <div className="flex items-center gap-4 text-[11px] font-mono text-zinc-400 pt-1 border-t border-zinc-800/80">
                  <span>
                    Observed: <strong className="text-red-400">{a.value}</strong>
                  </span>
                  <span>Limit: {a.limit}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Matched Operator Notes */}
      <section className="space-y-3">
        <div className="flex items-center justify-between border-b border-zinc-800 pb-2">
          <h2 className="font-mono text-sm uppercase tracking-wider text-zinc-200 font-bold flex items-center gap-2">
            <FileText className="w-4 h-4 text-blue-400" />
            Matched Maintenance & Shift Notes ({machine.notes.length})
          </h2>
          <span className="text-xs font-mono text-zinc-400">Logbook Correlation</span>
        </div>

        {machine.notes.length === 0 ? (
          <div className="p-4 rounded bg-zinc-900 border border-zinc-800 text-xs font-mono text-zinc-400">
            No maintenance records or shift log entries paired with this machine in the dataset.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {machine.notes.map((n) => (
              <div
                key={n.id}
                className="bg-zinc-900 border border-zinc-800 rounded-lg p-3.5 space-y-2 hover:border-zinc-700 transition"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => handleChipClick(n.id)}
                      className="px-2 py-0.5 rounded bg-blue-950/80 text-blue-300 font-mono text-xs font-bold border border-blue-500/40 hover:bg-blue-900"
                    >
                      [{n.id}]
                    </button>
                    <span className="font-mono text-xs text-zinc-300">{n.author}</span>
                  </div>
                  <span className="text-[11px] font-mono text-zinc-400">{n.timestamp}</span>
                </div>
                <p className="text-xs font-sans text-zinc-300 leading-relaxed italic">
                  "{n.content}"
                </p>
                <div className="flex flex-wrap gap-1 pt-1">
                  {n.tags.map((t) => (
                    <span
                      key={t}
                      className="px-1.5 py-0.5 rounded bg-zinc-950 text-zinc-400 text-[10px] font-mono"
                    >
                      #{t}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Data Warnings (if any) */}
      {machine.warnings.length > 0 && (
        <section className="space-y-3">
          <div className="flex items-center justify-between border-b border-zinc-800 pb-2">
            <h2 className="font-mono text-sm uppercase tracking-wider text-sky-300 font-bold flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-sky-400" />
              Data Warnings & Telemetry Hygiene ({machine.warnings.length})
            </h2>
            <span className="text-xs font-mono text-sky-400">Signal Ingest Flags</span>
          </div>

          <div className="p-4 rounded-lg bg-sky-950/20 border border-sky-500/30 space-y-2">
            <ul className="space-y-1.5 font-mono text-xs text-sky-200 list-disc list-inside">
              {machine.warnings.map((w, idx) => (
                <li key={idx}>{w}</li>
              ))}
            </ul>
          </div>
        </section>
      )}

      {/* 5 Sensor Charts */}
      <section className="space-y-4 pt-2">
        <div className="flex items-center justify-between border-b border-zinc-800 pb-2">
          <div>
            <span className="font-mono text-xs uppercase tracking-widest text-amber-500 font-semibold">
              Telemetry Traces
            </span>
            <h2 className="text-lg font-mono font-bold text-zinc-100">
              Sensor readings ({readings.length ? `${readings[0].displayTime} to ${readings[readings.length - 1].displayTime}` : 'no readings'})
            </h2>
          </div>
          <span className="text-xs font-mono text-zinc-400 hidden sm:inline">
            {readings.length} readings
          </span>
        </div>

        <div className="space-y-4">
          {sensors.map((sc, idx) => (
            <SensorChart
              key={sc.key}
              title={sc.label}
              dataKey={sc.key}
              unit={sc.unit}
              upperLimit={sc.warn_high ?? undefined}
              lowerLimit={sc.warn_low ?? undefined}
              data={readings}
              strokeColor={['#f59e0b', '#ef4444', '#38bdf8', '#fb923c', '#a855f7', '#22c55e'][idx % 6]}
            />
          ))}
        </div>
      </section>

      {/* Evidence Side Drawer */}
      <EvidenceDrawer
        isOpen={drawerOpen}
        evidence={selectedEvidence}
        onClose={() => setDrawerOpen(false)}
      />
    </div>
  );
};
