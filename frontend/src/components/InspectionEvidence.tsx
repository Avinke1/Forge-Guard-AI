import React, { useEffect, useRef, useState } from 'react';
import { useParams } from 'react-router-dom';
import {
  Paperclip,
  Plus,
  Trash2,
  AlertCircle,
  Lock,
  FileText,
  Film,
  Music,
  X,
} from 'lucide-react';
import { addFile, listFiles, removeFile, StoredEvidence } from '../lib/evidenceStore';

/**
 * Inspection evidence (attachments v2): photos, videos, audio and documents for the technician.
 * Saved on this device only (IndexedDB, see lib/evidenceStore.ts). Never uploaded, never sent to the AI.
 * The machine comes from the page URL (/machines/:id); MachinePage mounts it with key={machine.id}.
 */

type Kind = 'image' | 'video' | 'audio' | 'text' | 'pdf';

const MB = 1024 * 1024;
const MAX_FILES = 8;
const TEXT_PREVIEW_CHARS = 2000;

// extension -> kind, allowed MIME types, size limit. A file must match BOTH its extension and its MIME type.
const RULES: Record<string, { kind: Kind; mimes: string[]; max: number }> = {
  jpg: { kind: 'image', mimes: ['image/jpeg'], max: 10 * MB },
  jpeg: { kind: 'image', mimes: ['image/jpeg'], max: 10 * MB },
  png: { kind: 'image', mimes: ['image/png'], max: 10 * MB },
  webp: { kind: 'image', mimes: ['image/webp'], max: 10 * MB },
  mp4: { kind: 'video', mimes: ['video/mp4'], max: 30 * MB },
  webm: { kind: 'video', mimes: ['video/webm'], max: 30 * MB },
  mp3: { kind: 'audio', mimes: ['audio/mpeg', 'audio/mp3'], max: 10 * MB },
  wav: { kind: 'audio', mimes: ['audio/wav', 'audio/x-wav', 'audio/wave', 'audio/vnd.wave'], max: 10 * MB },
  m4a: { kind: 'audio', mimes: ['audio/mp4', 'audio/x-m4a', 'audio/m4a'], max: 10 * MB },
  txt: { kind: 'text', mimes: ['text/plain'], max: 5 * MB },
  pdf: { kind: 'pdf', mimes: ['application/pdf'], max: 5 * MB },
};
const ACCEPT = [...Object.keys(RULES).map((e) => `.${e}`), ...new Set(Object.values(RULES).flatMap((r) => r.mimes))].join(',');

const KIND_LABEL: Record<Kind, string> = { image: 'Image', video: 'Video', audio: 'Audio', text: 'Text', pdf: 'PDF' };

interface Item {
  id: string;
  name: string;
  type: string;
  size: number;
  addedAt: string;
  kind: Kind;
  url: string;
  saved: boolean; // false = kept in memory only (IndexedDB failed)
}

function extensionOf(name: string): string {
  const dot = name.lastIndexOf('.');
  return dot >= 0 ? name.slice(dot + 1).toLowerCase() : '';
}

/** null = accepted, otherwise a plain reason why the file is rejected. */
function rejectReason(file: File): string | null {
  const ext = extensionOf(file.name);
  const rule = RULES[ext];
  if (!rule) {
    return 'this file type is not allowed (images jpg/png/webp, video mp4/webm, audio mp3/wav/m4a, text txt/pdf).';
  }
  const mime = (file.type || '').toLowerCase();
  if (!rule.mimes.includes(mime)) {
    return `the file content type (${mime || 'unknown'}) does not match its .${ext} extension.`;
  }
  if (file.size > rule.max) {
    return `${formatSize(file.size)} is over the ${rule.max / MB} MB limit for ${KIND_LABEL[rule.kind].toLowerCase()} files.`;
  }
  return null;
}

function kindOf(name: string): Kind {
  return RULES[extensionOf(name)]?.kind ?? 'text';
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < MB) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / MB).toFixed(1)} MB`;
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  return isNaN(d.getTime()) ? iso : d.toLocaleString();
}

function newId(): string {
  try {
    if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') return crypto.randomUUID();
  } catch {
    /* fall through */
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

function toItem(r: StoredEvidence, saved: boolean): Item {
  return {
    id: r.id,
    name: r.name,
    type: r.type,
    size: r.size,
    addedAt: r.added_at,
    kind: kindOf(r.name),
    url: URL.createObjectURL(r.blob),
    saved,
  };
}

export const InspectionEvidence: React.FC<{ machineId?: string }> = ({ machineId }) => {
  const params = useParams<{ id: string }>();
  const machine = machineId || params.id || 'unknown';

  const [items, setItems] = useState<Item[]>([]);
  const [texts, setTexts] = useState<Record<string, string>>({});
  const [messages, setMessages] = useState<string[]>([]);
  const [storageProblem, setStorageProblem] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState(false);
  const [fullImage, setFullImage] = useState<Item | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const itemsRef = useRef<Item[]>([]);
  itemsRef.current = items;

  // Load saved files for this machine; free every object URL when leaving the page.
  useEffect(() => {
    let cancelled = false;
    listFiles(machine)
      .then((rows) => {
        if (cancelled) return;
        const loaded = rows.map((r) => toItem(r, true));
        setItems(loaded);
        rows.filter((r) => kindOf(r.name) === 'text').forEach((r) => loadText(r.id, r.blob));
      })
      .catch(() => {
        if (!cancelled) setStorageProblem(true);
      });
    return () => {
      cancelled = true;
      itemsRef.current.forEach((it) => URL.revokeObjectURL(it.url));
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [machine]);

  // Close the full-size image with Escape.
  useEffect(() => {
    if (!fullImage) return;
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setFullImage(null);
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [fullImage]);

  function loadText(id: string, blob: Blob) {
    blob
      .slice(0, TEXT_PREVIEW_CHARS * 4) // enough bytes for 2,000 characters
      .text()
      .then((t) => setTexts((prev) => ({ ...prev, [id]: t.slice(0, TEXT_PREVIEW_CHARS) })))
      .catch(() => setTexts((prev) => ({ ...prev, [id]: '(preview not available)' })));
  }

  async function handleFiles(list: FileList | File[] | null | undefined) {
    if (!list || busy) return;
    const files = Array.from(list);
    if (files.length === 0) return;
    setBusy(true);
    const problems: string[] = [];
    try {
      let count = itemsRef.current.length;
      for (const file of files) {
        try {
          const reason = rejectReason(file);
          if (reason) {
            problems.push(`${file.name}: ${reason}`);
            continue;
          }
          if (count >= MAX_FILES) {
            problems.push(`${file.name}: not added - the limit is ${MAX_FILES} files per machine.`);
            continue;
          }
          const record: StoredEvidence = {
            id: newId(),
            machine_id: machine,
            name: file.name,
            type: file.type,
            size: file.size,
            added_at: new Date().toISOString(),
            blob: file,
          };
          let saved = true;
          try {
            await addFile(record);
          } catch {
            saved = false;
            setStorageProblem(true);
          }
          const item = toItem(record, saved);
          count += 1;
          setItems((prev) => [...prev, item]);
          if (item.kind === 'text') loadText(item.id, file);
        } catch {
          problems.push(`${file.name}: could not be added.`);
        }
      }
    } finally {
      setMessages(problems);
      setBusy(false);
      if (inputRef.current) inputRef.current.value = ''; // allow choosing the same file again
    }
  }

  async function handleRemove(item: Item) {
    try {
      if (item.saved) await removeFile(item.id);
    } catch {
      setStorageProblem(true);
    }
    URL.revokeObjectURL(item.url);
    setItems((prev) => prev.filter((it) => it.id !== item.id));
    setTexts((prev) => {
      const next = { ...prev };
      delete next[item.id];
      return next;
    });
    if (fullImage?.id === item.id) setFullImage(null);
    setMessages([]);
  }

  const full = items.length >= MAX_FILES;

  return (
    <section aria-labelledby="inspection-evidence-heading" className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-zinc-800 pb-2">
        <h2
          id="inspection-evidence-heading"
          className="font-mono text-sm uppercase tracking-wider text-zinc-200 font-bold flex items-center gap-2"
        >
          <Paperclip className="w-4 h-4 text-amber-400" />
          Inspection evidence ({items.length}/{MAX_FILES})
        </h2>
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          disabled={full || busy}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-500 hover:bg-amber-400 disabled:opacity-50 disabled:cursor-not-allowed text-stone-950 font-mono text-xs font-bold transition focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-500"
        >
          <Plus className="w-4 h-4" />
          {full ? `Limit reached (${MAX_FILES} files)` : 'Add evidence'}
        </button>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={ACCEPT}
          className="hidden"
          aria-hidden="true"
          tabIndex={-1}
          onChange={(e) => handleFiles(e.target.files)}
        />
      </div>

      <p className="flex items-start gap-2 p-2.5 rounded bg-zinc-900 border border-zinc-800 text-xs font-mono text-zinc-300">
        <Lock className="w-3.5 h-3.5 text-emerald-400 shrink-0 mt-0.5" />
        Photos, videos, audio and documents for the technician. Saved on this device only. Not sent to the AI.
      </p>

      {storageProblem && (
        <p role="status" className="p-2.5 rounded bg-amber-950/40 border border-amber-500/40 text-xs font-mono text-amber-200">
          Could not save - lost on refresh.
        </p>
      )}

      <div
        onDragOver={(e) => {
          e.preventDefault();
          if (!full) setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          handleFiles(e.dataTransfer?.files);
        }}
        className={`rounded-lg border-2 border-dashed p-4 text-center text-xs font-mono transition ${
          dragging ? 'border-amber-400 bg-amber-500/10 text-amber-200' : 'border-zinc-700 text-zinc-400'
        }`}
      >
        {busy
          ? 'Adding files...'
          : full
          ? `${MAX_FILES} files attached - remove one to add another.`
          : 'Drag and drop files here, or use "Add evidence". Images jpg/png/webp up to 10 MB, video mp4/webm up to 30 MB, audio mp3/wav/m4a up to 10 MB, txt/pdf up to 5 MB.'}
      </div>

      {messages.length > 0 && (
        <div role="alert" className="p-3 rounded bg-red-950/50 border border-red-500/50 space-y-1">
          {messages.map((msg, i) => (
            <p key={i} className="flex items-start gap-2 text-xs font-mono text-red-200">
              <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5 text-red-400" />
              {msg}
            </p>
          ))}
        </div>
      )}

      {items.length > 0 && (
        <ul className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {items.map((it) => (
            <li key={it.id} className="bg-zinc-900 border border-zinc-800 rounded-lg overflow-hidden flex flex-col">
              <div className="bg-zinc-950">
                {it.kind === 'image' && (
                  <button
                    type="button"
                    onClick={() => setFullImage(it)}
                    className="block w-full focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-500"
                    title="Show full size"
                  >
                    <img src={it.url} alt={it.name} className="w-full h-40 object-cover" />
                  </button>
                )}
                {it.kind === 'video' && (
                  <video controls preload="metadata" src={it.url} className="w-full h-40 bg-black">
                    <Film className="w-6 h-6" />
                  </video>
                )}
                {it.kind === 'audio' && (
                  <div className="p-3 flex flex-col gap-2">
                    <Music className="w-6 h-6 text-amber-400" />
                    <audio controls src={it.url} className="w-full" />
                  </div>
                )}
                {it.kind === 'text' && (
                  <pre className="h-40 overflow-auto p-2 text-[11px] leading-snug text-zinc-300 whitespace-pre-wrap break-words font-mono">
                    {texts[it.id] ?? 'Loading preview...'}
                  </pre>
                )}
                {it.kind === 'pdf' && (
                  <a
                    href={it.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="h-40 flex flex-col items-center justify-center gap-1 text-amber-400 hover:text-amber-300 font-mono text-xs"
                  >
                    <FileText className="w-8 h-8" />
                    Open PDF
                  </a>
                )}
              </div>
              <div className="p-2.5 flex items-start justify-between gap-2">
                <div className="min-w-0 font-mono">
                  <p className="text-xs text-zinc-100 truncate" title={it.name}>
                    {it.name}
                  </p>
                  <p className="text-[10px] text-zinc-400">
                    {KIND_LABEL[it.kind]} · {formatSize(it.size)} · {formatDate(it.addedAt)}
                  </p>
                  {!it.saved && <p className="text-[10px] text-amber-300">Not saved - lost on refresh</p>}
                </div>
                <button
                  type="button"
                  onClick={() => handleRemove(it)}
                  aria-label={`Remove ${it.name}`}
                  className="shrink-0 inline-flex items-center gap-1 px-2 py-1 rounded text-[11px] font-mono text-zinc-300 hover:text-red-300 hover:bg-red-950/60 border border-zinc-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-500"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                  Remove
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}

      {fullImage && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label={fullImage.name}
          onClick={() => setFullImage(null)}
          className="fixed inset-0 z-50 bg-black/85 flex items-center justify-center p-4"
        >
          <button
            type="button"
            onClick={() => setFullImage(null)}
            aria-label="Close full-size image"
            className="absolute top-4 right-4 p-2 rounded bg-zinc-800 text-zinc-100 hover:bg-zinc-700"
          >
            <X className="w-5 h-5" />
          </button>
          <img
            src={fullImage.url}
            alt={fullImage.name}
            onClick={(e) => e.stopPropagation()}
            className="max-w-full max-h-full object-contain rounded"
          />
        </div>
      )}
    </section>
  );
};
