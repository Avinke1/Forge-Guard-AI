import React from 'react';
import { AlertOctagon, AlertTriangle, Info, CheckCircle2 } from 'lucide-react';
import { PriorityLevel } from '../types';

interface PriorityBadgeProps {
  priority: PriorityLevel;
  size?: 'sm' | 'md' | 'lg';
}

export const PriorityBadge: React.FC<PriorityBadgeProps> = ({ priority, size = 'md' }) => {
  const configs = {
    HIGH: {
      bg: 'bg-red-950/80 border-red-500/50 text-red-200',
      icon: AlertOctagon,
      iconColor: 'text-red-400',
      dotColor: 'bg-red-500',
      label: 'HIGH',
    },
    MEDIUM: {
      bg: 'bg-amber-950/80 border-amber-500/50 text-amber-200',
      icon: AlertTriangle,
      iconColor: 'text-amber-400',
      dotColor: 'bg-amber-500',
      label: 'MEDIUM',
    },
    LOW: {
      bg: 'bg-sky-950/70 border-sky-500/40 text-sky-200',
      icon: Info,
      iconColor: 'text-sky-400',
      dotColor: 'bg-sky-400',
      label: 'LOW',
    },
    OK: {
      bg: 'bg-emerald-950/70 border-emerald-500/40 text-emerald-200',
      icon: CheckCircle2,
      iconColor: 'text-emerald-400',
      dotColor: 'bg-emerald-400',
      label: 'OK',
    },
  };

  const config = configs[priority] || configs.OK;
  const Icon = config.icon;

  const sizeStyles = {
    sm: 'text-xs px-2 py-0.5 gap-1.5 font-mono',
    md: 'text-xs sm:text-sm px-2.5 py-1 gap-1.5 font-mono font-semibold',
    lg: 'text-sm sm:text-base px-3 py-1.5 gap-2 font-mono font-bold',
  };

  return (
    <span
      className={`inline-flex items-center rounded border shadow-sm tracking-wider uppercase ${config.bg} ${sizeStyles[size]}`}
    >
      <Icon className={`w-3.5 h-3.5 shrink-0 ${config.iconColor}`} />
      <span>{config.label}</span>
    </span>
  );
};
