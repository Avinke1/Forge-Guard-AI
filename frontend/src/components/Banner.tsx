import React from 'react';
import { AlertTriangle } from 'lucide-react';
import { USE_MOCK } from '../api';

export const Banner: React.FC = () => {
  if (!USE_MOCK) return null;
  return (
    <div
      role="status"
      className="w-full bg-amber-400 text-stone-950 font-mono text-xs sm:text-sm font-semibold py-1.5 px-3 flex items-center justify-center gap-2 border-b border-amber-500 shadow-inner select-none tracking-wide text-center"
    >
      <AlertTriangle className="w-4 h-4 shrink-0 text-stone-950" aria-hidden="true" />
      <span>MOCK DATA - for interface testing only, not real analysis</span>
    </div>
  );
};
