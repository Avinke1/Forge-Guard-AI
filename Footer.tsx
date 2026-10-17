import React from 'react';
import { ShieldAlert } from 'lucide-react';

export const Footer: React.FC = () => {
  return (
    <footer className="w-full border-t border-zinc-800 bg-zinc-950/90 text-zinc-400 py-6 px-4 mt-auto">
      <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4 text-xs">
        <div className="flex items-center gap-2 text-zinc-300 font-mono">
          <ShieldAlert className="w-4 h-4 text-amber-500 shrink-0" />
          <span className="font-semibold tracking-wider text-zinc-200">FORGEGUARD AI</span>
          <span className="text-zinc-600">|</span>
          <span className="text-zinc-400">Industrial Signal Triage</span>
        </div>
        <p className="text-zinc-300 text-center sm:text-right font-medium">
          ForgeGuard suggests what to inspect. A qualified technician makes the decision.
        </p>
      </div>
    </footer>
  );
};
