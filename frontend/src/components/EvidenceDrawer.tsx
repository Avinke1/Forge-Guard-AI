import React, { useEffect } from 'react';
import { X, AlertCircle, FileText, Activity, AlertTriangle, ShieldCheck } from 'lucide-react';
import { EvidenceDetail } from '../types';

interface EvidenceDrawerProps {
  evidence: EvidenceDetail | null;
  isOpen: boolean;
  onClose: () => void;
}

export const EvidenceDrawer: React.FC<EvidenceDrawerProps> = ({
  evidence,
  isOpen,
  onClose,
}) => {
  // Listen for Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen || !evidence) return null;

  const isUnsupported = !!evidence.isUnsupported || evidence.type === 'unsupported';

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="drawer-title"
      className="fixed inset-0 z-50 overflow-hidden"
    >
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/70 backdrop-blur-sm transition-opacity"
        onClick={onClose}
        aria-hidden="true"
      />

      <div className="fixed inset-y-0 right-0 max-w-full flex pl-10">
        <div className="w-screen max-w-md bg-zinc-900 border-l border-zinc-700 shadow-2xl flex flex-col text-zinc-100">
          {/* Header */}
          <div className="p-4 sm:p-5 border-b border-zinc-800 flex items-center justify-between bg-zinc-950/80">
            <div className="flex items-center gap-2.5">
              {isUnsupported ? (
                <div className="p-1.5 rounded bg-red-950 border border-red-500/40 text-red-400">
                  <AlertCircle className="w-5 h-5" />
                </div>
              ) : evidence.type === 'anomaly' ? (
                <div className="p-1.5 rounded bg-amber-950 border border-amber-500/40 text-amber-400">
                  <AlertTriangle className="w-5 h-5" />
                </div>
              ) : evidence.type === 'note' ? (
                <div className="p-1.5 rounded bg-blue-950 border border-blue-500/40 text-blue-400">
                  <FileText className="w-5 h-5" />
                </div>
              ) : (
                <div className="p-1.5 rounded bg-emerald-950 border border-emerald-500/40 text-emerald-400">
                  <Activity className="w-5 h-5" />
                </div>
              )}
              <div>
                <span className="text-xs uppercase font-mono tracking-widest text-zinc-400">
                  Evidence Inspector
                </span>
                <h2 id="drawer-title" className="text-base font-bold font-mono text-zinc-100">
                  {evidence.title}
                </h2>
              </div>
            </div>

            <button
              type="button"
              onClick={onClose}
              className="p-1.5 rounded-md text-zinc-400 hover:text-white hover:bg-zinc-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-500"
              aria-label="Close drawer"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Body */}
          <div className="p-5 flex-1 overflow-y-auto space-y-5 font-mono text-xs sm:text-sm">
            {isUnsupported ? (
              <div className="p-4 rounded-lg bg-red-950/40 border border-red-500/40 text-red-200 space-y-3">
                <div className="flex items-center gap-2 font-bold text-red-400 text-sm">
                  <AlertCircle className="w-5 h-5 shrink-0" />
                  <span>Validation Warning</span>
                </div>
                <p className="text-sm font-semibold text-red-300">
                  Not found in this analysis - this claim is unsupported
                </p>
                <p className="text-xs text-red-400/90 leading-relaxed font-sans">
                  The generated report referenced identifier <code className="bg-red-950 px-1 py-0.5 rounded border border-red-500/30 text-white font-mono">{evidence.id}</code>, which does not correlate to any confirmed sensor anomaly, threshold breach, or maintenance record in the current telemetry window.
                </p>
              </div>
            ) : (
              <>
                {evidence.subtitle && (
                  <div className="p-3 bg-zinc-950/60 rounded border border-zinc-800 text-zinc-300 font-sans text-sm">
                    {evidence.subtitle}
                  </div>
                )}

                {evidence.timestamp && (
                  <div className="flex items-center justify-between py-2 border-b border-zinc-800 text-xs">
                    <span className="text-zinc-400">Observed Timestamp:</span>
                    <span className="text-amber-400 font-semibold">{evidence.timestamp}</span>
                  </div>
                )}

                {/* Key-Value Details */}
                {Object.keys(evidence.data).length > 0 && (
                  <div className="space-y-2">
                    <div className="text-xs text-zinc-400 uppercase tracking-wider font-semibold">
                      Telemetry Record Data
                    </div>
                    <div className="bg-zinc-950 rounded border border-zinc-800 overflow-hidden divide-y divide-zinc-800">
                      {Object.entries(evidence.data).map(([key, val]) => (
                        <div key={key} className="flex justify-between items-center px-3 py-2 text-xs">
                          <span className="text-zinc-400">{key}</span>
                          <span className="text-zinc-100 font-bold">{val}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Maintenance Note text */}
                {evidence.noteText && (
                  <div className="space-y-2">
                    <div className="text-xs text-zinc-400 uppercase tracking-wider font-semibold">
                      Logged Operator Note Content
                    </div>
                    <div className="p-3.5 bg-zinc-950 rounded border border-zinc-800 text-zinc-200 font-sans text-sm leading-relaxed border-l-2 border-l-amber-500">
                      "{evidence.noteText}"
                    </div>
                  </div>
                )}

                <div className="p-3 rounded bg-zinc-950/60 border border-zinc-800 text-xs text-zinc-400 flex items-start gap-2">
                  <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                  <span className="font-sans">
                    Traceable evidence authenticated against pipeline telemetry stream.
                  </span>
                </div>
              </>
            )}
          </div>

          {/* Footer */}
          <div className="p-4 border-t border-zinc-800 bg-zinc-950 flex justify-end">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-mono font-medium rounded transition focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-500"
            >
              Close (Esc)
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
