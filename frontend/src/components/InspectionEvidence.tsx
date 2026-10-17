import React, { useEffect, useRef, useState } from 'react';
import { Paperclip, FileText, Trash2, Upload, AlertCircle, Lock } from 'lucide-react';

/**
 * Inspection evidence: photos (jpg/png) and documents (pdf) the technician attaches on this device.
 * Files stay in the browser only (object URLs). They are never uploaded and never sent to the AI.
 * Mount it with key={machineId} so each machine starts with an empty list.
 */

const MAX_FILES = 5;
const MAX_BYTES = 5 * 1024 * 1024;
const IMAGE_TYPES = ['image/jpeg', 'image/png'];
const PDF_TYPE = 'application/pdf';

interface Attachment {
  id: string;
  name: string;
  size: number;
  kind: 'image' | 'pdf';
  url: string;
}

function kindOf(file: File): 'image' | 'pdf' | null {
  const name = file.name.toLowerCase();
  if (IMAGE_TYPES.includes(file.type) || /\.(jpe?g|png)$/.test(name)) return 'image';
  if (file.type === PDF_TYPE || name.endsWith('.pdf')) return 'pdf';
  return null;
}

function formatSize(bytes: number): string {
  return bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export const InspectionEvidence: React.FC = () => {
  const [items, setItems] = useState<Attachment[]>([]);
  const [errors, setErrors] = useState<string[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);
  const itemsRef = useRef<Attachment[]>([]);
  itemsRef.current = items;

  // Free every object URL when the page is left (or the machine changes).
  useEffect(() => () => itemsRef.current.forEach((a) => URL.revokeObjectURL(a.url)), []);

  const handleFiles = (list: FileList | null) => {
    if (!list) return;
    const problems: string[] = [];
    const added: Attachment[] = [];
    for (const file of Array.from(list)) {
      const kind = kindOf(file);
      if (!kind) {
        problems.push(`${file.name}: only JPG, PNG or PDF files can be attached.`);
      } else if (file.size > MAX_BYTES) {
        problems.push(`${file.name}: ${formatSize(file.size)} is over the 5 MB limit.`);
      } else if (items.length + added.length >= MAX_FILES) {
        problems.push(`${file.name}: not added - the limit is ${MAX_FILES} files.`);
      } else {
        added.push({
          id: `${Date.now()}-${added.length}-${file.name}`,
          name: file.name,
          size: file.size,
          kind,
          url: URL.createObjectURL(file),
        });
      }
    }
    setItems((prev) => [...prev, ...added]);
    setErrors(problems);
    if (inputRef.current) inputRef.current.value = ''; // allow choosing the same file again
  };

  const remove = (id: string) => {
    setItems((prev) => {
      const gone = prev.find((a) => a.id === id);
      if (gone) URL.revokeObjectURL(gone.url);
      return prev.filter((a) => a.id !== id);
    });
    setErrors([]);
  };

  const full = items.length >= MAX_FILES;

  return (
    <section aria-labelledby="inspection-evidence-heading" className="space-y-3">
      <div className="flex items-center justify-between border-b border-zinc-800 pb-2">
        <h2
          id="inspection-evidence-heading"
          className="font-mono text-sm uppercase tracking-wider text-zinc-200 font-bold flex items-center gap-2"
        >
          <Paperclip className="w-4 h-4 text-amber-400" />
          Inspection evidence ({items.length}/{MAX_FILES})
        </h2>
        <span className="text-xs font-mono text-zinc-400">JPG, PNG or PDF - max 5 MB each</span>
      </div>

      <p className="flex items-center gap-2 p-2.5 rounded bg-zinc-900 border border-zinc-800 text-xs font-mono text-zinc-300">
        <Lock className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
        Attachments stay on this device and are not sent to the AI.
      </p>

      <div>
        <input
          ref={inputRef}
          id="inspection-evidence-input"
          type="file"
          accept="image/jpeg,image/png,application/pdf,.jpg,.jpeg,.png,.pdf"
          multiple
          className="sr-only"
          disabled={full}
          onChange={(e) => handleFiles(e.target.files)}
        />
        <label
          htmlFor="inspection-evidence-input"
          className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg font-mono text-xs font-bold transition ${
            full
              ? 'bg-zinc-800 text-zinc-500 cursor-not-allowed'
              : 'bg-zinc-800 hover:bg-zinc-700 text-zinc-100 cursor-pointer border border-zinc-700'
          }`}
        >
          <Upload className="w-4 h-4" />
          {full ? 'Limit reached (5 files)' : 'Attach photos or PDFs'}
        </label>
      </div>

      {errors.length > 0 && (
        <div role="alert" className="p-3 rounded bg-red-950/50 border border-red-500/50 space-y-1">
          {errors.map((msg, i) => (
            <p key={i} className="flex items-start gap-2 text-xs font-mono text-red-200">
              <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5 text-red-400" />
              {msg}
            </p>
          ))}
        </div>
      )}

      {items.length === 0 ? (
        <div className="p-4 rounded bg-zinc-900 border border-zinc-800 text-xs font-mono text-zinc-400">
          No inspection evidence attached yet.
        </div>
      ) : (
        <ul className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
          {items.map((a) => (
            <li key={a.id} className="bg-zinc-900 border border-zinc-800 rounded-lg overflow-hidden flex flex-col">
              {a.kind === 'image' ? (
                <a href={a.url} target="_blank" rel="noopener noreferrer" title={`Open ${a.name}`}>
                  <img src={a.url} alt={a.name} className="w-full h-28 object-cover bg-zinc-950" />
                </a>
              ) : (
                <a
                  href={a.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="h-28 flex flex-col items-center justify-center gap-1 bg-zinc-950 text-amber-400 hover:text-amber-300 font-mono text-xs"
                >
                  <FileText className="w-8 h-8" />
                  Open PDF
                </a>
              )}
              <div className="p-2 flex items-center justify-between gap-2">
                <div className="min-w-0">
                  <p className="text-[11px] font-mono text-zinc-200 truncate" title={a.name}>
                    {a.name}
                  </p>
                  <p className="text-[10px] font-mono text-zinc-500">{formatSize(a.size)}</p>
                </div>
                <button
                  type="button"
                  onClick={() => remove(a.id)}
                  aria-label={`Remove ${a.name}`}
                  className="p-1.5 rounded text-zinc-400 hover:text-red-300 hover:bg-red-950/60 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-500"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
};
