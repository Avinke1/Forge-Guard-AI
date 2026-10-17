import React from 'react';
import { Link } from 'react-router-dom';
import { AlertCircle, ArrowLeft, Home } from 'lucide-react';

export const NotFoundPage: React.FC = () => {
  return (
    <div className="py-20 text-center font-mono space-y-5">
      <div className="inline-flex p-4 rounded-full bg-zinc-900 border border-zinc-800 text-amber-500">
        <AlertCircle className="w-10 h-10" />
      </div>

      <div className="space-y-2">
        <h1 className="text-3xl font-black text-zinc-100">Page not found</h1>
        <p className="text-xs sm:text-sm text-zinc-400 max-w-md mx-auto font-sans">
          The requested route does not exist in ForgeGuard AI.
        </p>
      </div>

      <div className="pt-4 flex justify-center gap-3 text-xs">
        <Link
          to="/"
          className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-amber-500 hover:bg-amber-400 text-stone-950 font-bold transition shadow"
        >
          <Home className="w-4 h-4" />
          <span>Go to Overview</span>
        </Link>
        <Link
          to="/queue"
          className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-200 font-semibold border border-zinc-700 transition"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Open Queue</span>
        </Link>
      </div>
    </div>
  );
};
