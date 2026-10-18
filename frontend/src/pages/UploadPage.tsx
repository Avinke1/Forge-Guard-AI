import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  UploadCloud,
  FileCheck,
  AlertCircle,
  CheckCircle2,
  Play,
  ArrowRight,
  Database,
  Layers,
  FileSpreadsheet,
} from 'lucide-react';
import { uploadReadings, runDemo, DatasetId } from '../api';
import { ValidationReport } from '../types';

export const UploadPage: React.FC = () => {
  const navigate = useNavigate();

  const [readingsFile, setReadingsFile] = useState<File | null>(null);
  const [notesFile, setNotesFile] = useState<File | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [validationReport, setValidationReport] = useState<ValidationReport | null>(null);

  const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10 MB

  const validateFile = (file: File, isReadings: boolean): boolean => {
    setErrorMessage(null);
    if (!file.name.toLowerCase().endsWith('.csv')) {
      setErrorMessage(
        `Invalid file type for ${file.name}. Only .csv tabular data files are accepted.`
      );
      return false;
    }
    if (file.size === 0) {
      setErrorMessage(`${file.name} is empty. Please choose a CSV file with a header row and data.`);
      return false;
    }
    if (file.size > MAX_FILE_SIZE) {
      setErrorMessage(
        `File ${file.name} exceeds the 10 MB limit (${(file.size / (1024 * 1024)).toFixed(2)} MB). Please trim the sample window.`
      );
      return false;
    }
    return true;
  };

  const handleReadingsChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      if (validateFile(file, true)) {
        setReadingsFile(file);
      }
    }
  };

  // Drag-and-drop onto the drop zones
  const dropProps = (isReadings: boolean) => ({
    onDragOver: (e: any) => {
      e.preventDefault();
    },
    onDrop: (e: any) => {
      e.preventDefault();
      const file: File | undefined = e.dataTransfer?.files?.[0];
      if (file && validateFile(file, isReadings)) {
        if (isReadings) setReadingsFile(file);
        else setNotesFile(file);
      }
    },
  });

  const handleNotesChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      if (validateFile(file, false)) {
        setNotesFile(file);
      }
    }
  };

  const [demoBusy, setDemoBusy] = useState<DatasetId | null>(null);

  // Demo buttons: the backend runs the analysis on its own stored demo dataset
  const handleLoadDemo = async (preset: 'fleet' | 'metro') => {
    const id: DatasetId = preset === 'fleet' ? 'synthetic_fleet' : 'metropt3';
    setErrorMessage(null);
    setValidationReport(null);
    setDemoBusy(id);
    try {
      const result = await runDemo(id);
      setValidationReport(result.validation);
      navigate('/queue'); // like the Overview page: a finished demo opens the inspection queue
    } catch (err: any) {
      setErrorMessage(err?.message || 'The demo could not be started.');
    } finally {
      setDemoBusy(null);
    }
  };

  const handleRunAnalysis = async () => {
    if (!readingsFile) {
      setErrorMessage('Please provide a readings.csv file to run analysis.');
      return;
    }

    setIsProcessing(true);
    setErrorMessage(null);

    try {
      const result = await uploadReadings(readingsFile, notesFile || undefined);
      setValidationReport(result.validation);
    } catch (err: any) {
      setErrorMessage(err.message || 'An unexpected error occurred while processing CSV.');
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="space-y-8 py-6 max-w-4xl mx-auto">
      {/* Header */}
      <div className="border-b border-zinc-800 pb-5">
        <span className="font-mono text-xs uppercase tracking-widest text-amber-500 font-semibold">
          Data Ingestion Pipeline
        </span>
        <h1 className="text-2xl sm:text-3xl font-bold font-mono text-zinc-100 mt-1">
          Upload machine readings and notes
        </h1>
        <p className="text-xs sm:text-sm text-zinc-400 font-sans mt-2">
          Ingest multi-channel machine sensor telemetry in .csv format. You may also provide an optional operator maintenance notes log for correlation.
        </p>
      </div>

      {/* Preset Demo Buttons */}
      <div className="p-4 rounded-xl bg-zinc-900 border border-zinc-800 space-y-3">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <span className="font-mono text-xs uppercase tracking-wider text-zinc-300 font-bold">
            Quick Ingest Presets:
          </span>
          <span className="text-[11px] font-mono text-zinc-500">Runs the analysis on the backend's demo data</span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 font-mono text-xs">
          <button
            type="button"
            onClick={() => handleLoadDemo('fleet')}
            disabled={demoBusy !== null || isProcessing}
            className="p-3 rounded-lg bg-zinc-950 hover:bg-zinc-800 border border-amber-500/30 hover:border-amber-500 text-left transition flex items-center justify-between group focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-500"
          >
            <div className="flex items-center gap-3">
              <Layers className="w-5 h-5 text-amber-500 shrink-0" />
              <div>
                <div className="font-bold text-zinc-200 group-hover:text-amber-400">
                  Synthetic fleet
                </div>
                <div className="text-[11px] text-zinc-400 font-sans">
                  6 machines + handover notes
                </div>
              </div>
            </div>
            <span className="text-amber-500 text-xs font-bold">{demoBusy === 'synthetic_fleet' ? 'Running...' : 'Run demo'}</span>
          </button>

          <button
            type="button"
            onClick={() => handleLoadDemo('metro')}
            disabled={demoBusy !== null || isProcessing}
            className="p-3 rounded-lg bg-zinc-950 hover:bg-zinc-800 border border-blue-500/30 hover:border-blue-400 text-left transition flex items-center justify-between group focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-500"
          >
            <div className="flex items-center gap-3">
              <Database className="w-5 h-5 text-blue-400 shrink-0" />
              <div>
                <div className="font-bold text-zinc-200 group-hover:text-blue-300">
                  MetroPT-3 (real data)
                </div>
                <div className="text-[11px] text-zinc-400 font-sans">
                  Metro train air compressor APU-01
                </div>
              </div>
            </div>
            <span className="text-blue-400 text-xs font-bold">{demoBusy === 'metropt3' ? 'Running...' : 'Run demo'}</span>
          </button>
        </div>
      </div>

      {/* Upload Form */}
      <div className="space-y-6">
        {/* Readings CSV Dropzone (Required) */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <label
              htmlFor="readings-upload"
              className="font-mono text-xs uppercase tracking-wider text-zinc-200 font-bold flex items-center gap-1.5"
            >
              <FileSpreadsheet className="w-4 h-4 text-amber-500" />
              <span>readings.csv</span>
              <span className="text-red-400 text-xs font-mono font-normal">(required)</span>
            </label>
            <span className="text-[11px] font-mono text-zinc-500">.csv only • max 10 MB</span>
          </div>

          <label
            htmlFor="readings-upload"
            {...dropProps(true)}
            className="border-2 border-dashed border-zinc-700 hover:border-amber-500/70 bg-zinc-900/60 rounded-xl p-6 flex flex-col items-center justify-center gap-2 cursor-pointer transition text-center group"
          >
            <UploadCloud className="w-8 h-8 text-zinc-400 group-hover:text-amber-400 transition" />
            <span className="font-mono text-xs text-zinc-300 group-hover:text-white font-medium">
              {readingsFile ? readingsFile.name : 'Click to select or drop readings.csv here'}
            </span>
            <span className="text-[11px] font-mono text-zinc-500">
              Columns: machine_id, timestamp, vibration_mm_s, temperature_c, pressure_bar, sound_db, rpm
            </span>
            <input
              id="readings-upload"
              type="file"
              accept=".csv"
              onChange={handleReadingsChange}
              className="sr-only"
            />
          </label>
        </div>

        {/* Notes CSV Dropzone (Optional) */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <label
              htmlFor="notes-upload"
              className="font-mono text-xs uppercase tracking-wider text-zinc-200 font-bold flex items-center gap-1.5"
            >
              <FileSpreadsheet className="w-4 h-4 text-blue-400" />
              <span>notes.csv</span>
              <span className="text-zinc-500 text-xs font-mono font-normal">(optional)</span>
            </label>
            <span className="text-[11px] font-mono text-zinc-500">.csv only • max 10 MB</span>
          </div>

          <label
            htmlFor="notes-upload"
            {...dropProps(false)}
            className="border-2 border-dashed border-zinc-800 hover:border-blue-500/70 bg-zinc-900/30 rounded-xl p-6 flex flex-col items-center justify-center gap-2 cursor-pointer transition text-center group"
          >
            <UploadCloud className="w-8 h-8 text-zinc-500 group-hover:text-blue-400 transition" />
            <span className="font-mono text-xs text-zinc-400 group-hover:text-white font-medium">
              {notesFile ? notesFile.name : 'Click to select or drop optional notes.csv'}
            </span>
            <span className="text-[11px] font-mono text-zinc-500">
              Columns: note_id, machine_id, timestamp, text
            </span>
            <input
              id="notes-upload"
              type="file"
              accept=".csv"
              onChange={handleNotesChange}
              className="sr-only"
            />
          </label>
        </div>

        {/* Friendly Error Message */}
        {errorMessage && (
          <div role="alert" className="p-4 rounded-lg bg-red-950/60 border border-red-500/50 flex items-start gap-3 text-red-200">
            <AlertCircle className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
            <div className="font-mono text-xs space-y-1">
              <div className="font-bold text-red-300">File Ingestion Issue</div>
              <div className="font-sans text-xs">{errorMessage}</div>
            </div>
          </div>
        )}

        {/* Action Button */}
        <div className="pt-2">
          <button
            type="button"
            onClick={handleRunAnalysis}
            disabled={!readingsFile || isProcessing}
            className="w-full sm:w-auto px-6 py-3 rounded-lg bg-amber-500 hover:bg-amber-400 disabled:opacity-40 disabled:cursor-not-allowed text-stone-950 font-mono text-sm font-bold transition flex items-center justify-center gap-2 shadow-lg shadow-amber-500/20 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-500"
          >
            {isProcessing ? (
              <>
                <div className="w-4 h-4 border-2 border-stone-950 border-t-transparent rounded-full animate-spin" />
                <span>Running analysis & validation...</span>
              </>
            ) : (
              <>
                <Play className="w-4 h-4 fill-stone-950" />
                <span>Run analysis</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Validation Report */}
      {validationReport && (
        <section
          aria-labelledby="validation-heading"
          className="rounded-xl border border-zinc-700 bg-zinc-900 p-6 space-y-5 shadow-2xl animate-in fade-in"
        >
          <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-5 h-5 text-emerald-400" />
              <h2 id="validation-heading" className="font-mono font-bold text-base text-zinc-100">
                Pipeline Ingestion Validation Report
              </h2>
            </div>
            <span className="font-mono text-xs text-emerald-400 font-semibold">
              Analysis complete
            </span>
          </div>

          {/* Metric Badges */}
          <div className="grid grid-cols-3 gap-3 font-mono text-center">
            <div className="p-3 rounded bg-zinc-950 border border-zinc-800">
              <div className="text-[11px] text-zinc-400">Total Rows In</div>
              <div className="text-xl font-bold text-zinc-100 mt-1">
                {validationReport.totalRows}
              </div>
            </div>

            <div className="p-3 rounded bg-emerald-950/40 border border-emerald-500/30">
              <div className="text-[11px] text-emerald-400">Rows Kept</div>
              <div className="text-xl font-bold text-emerald-300 mt-1">
                {validationReport.keptRows}
              </div>
            </div>

            <div className="p-3 rounded bg-red-950/40 border border-red-500/30">
              <div className="text-[11px] text-red-400">Rows Dropped</div>
              <div className="text-xl font-bold text-red-300 mt-1">
                {validationReport.droppedRows}
              </div>
            </div>
          </div>

          {/* Issue Logs */}
          <div className="space-y-2 font-mono text-xs">
            <span className="text-zinc-400 uppercase tracking-wider font-semibold">
              Sanitization & Hygiene Audit:
            </span>
            <ul className="bg-zinc-950 rounded-lg p-3 border border-zinc-800 space-y-1.5 text-zinc-300">
              {validationReport.details.map((detail, idx) => (
                <li key={idx} className="flex items-start gap-2">
                  <span className="text-amber-500">›</span>
                  <span>{detail}</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="pt-2 flex justify-end">
            <button
              type="button"
              onClick={() => navigate('/queue')}
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-amber-500 hover:bg-amber-400 text-stone-950 font-mono text-xs font-bold transition shadow focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-500"
            >
              <span>Proceed to Inspection Queue</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </section>
      )}
    </div>
  );
};
