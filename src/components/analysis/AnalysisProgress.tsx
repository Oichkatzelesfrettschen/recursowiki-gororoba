'use client';

import React from 'react';
import type { AnalysisPhase } from '@/types/analysis';

interface AnalysisProgressProps {
  phase: AnalysisPhase;
  progress: number;
  message?: string;
}

const PHASES: Array<{ key: AnalysisPhase; label: string }> = [
  { key: 'queued', label: 'Queued' },
  { key: 'detecting', label: 'Detecting' },
  { key: 'provisioning', label: 'Provisioning' },
  { key: 'running_tools', label: 'Running Tools' },
  { key: 'normalizing', label: 'Normalizing' },
  { key: 'merging', label: 'Merging' },
  { key: 'agents', label: 'AI Analysis' },
  { key: 'complete', label: 'Complete' },
];

function phaseIndex(phase: AnalysisPhase): number {
  const idx = PHASES.findIndex((p) => p.key === phase);
  return idx >= 0 ? idx : 0;
}

export default function AnalysisProgress({
  phase,
  progress,
  message,
}: AnalysisProgressProps) {
  const currentIdx = phaseIndex(phase);
  const pct = Math.max(0, Math.min(100, progress * 100));

  return (
    <div className="card-japanese p-6 rounded-lg space-y-4">
      {/* Progress bar */}
      <div className="w-full bg-[var(--background)]/50 rounded-full h-2 overflow-hidden border border-[var(--border-color)]">
        <div
          className="bg-[var(--accent-primary)] h-2 rounded-full transition-all duration-500 ease-in-out"
          style={{ width: `${pct}%` }}
        />
      </div>

      {/* Phase steps */}
      <div className="flex items-center justify-between">
        {PHASES.map((p, i) => {
          const isComplete = i < currentIdx;
          const isCurrent = i === currentIdx;
          return (
            <div key={p.key} className="flex flex-col items-center gap-1">
              <div
                className={`w-3 h-3 rounded-full transition-colors ${
                  isComplete
                    ? 'bg-[var(--accent-primary)]'
                    : isCurrent
                      ? 'bg-[var(--highlight)] animate-pulse'
                      : 'bg-[var(--border-color)]'
                }`}
              />
              <span
                className={`text-[10px] ${
                  isCurrent
                    ? 'text-[var(--foreground)] font-semibold'
                    : isComplete
                      ? 'text-[var(--accent-primary)]'
                      : 'text-[var(--muted)]'
                }`}
              >
                {p.label}
              </span>
            </div>
          );
        })}
      </div>

      {/* Status message */}
      {message && (
        <p className="text-sm text-[var(--muted)] text-center">{message}</p>
      )}

      {/* Loading animation */}
      {phase !== 'complete' && phase !== 'failed' && (
        <div className="flex items-center justify-center gap-2">
          <div className="w-2 h-2 bg-[var(--accent-primary)]/70 rounded-full animate-pulse" />
          <div className="w-2 h-2 bg-[var(--accent-primary)]/70 rounded-full animate-pulse delay-75" />
          <div className="w-2 h-2 bg-[var(--accent-primary)]/70 rounded-full animate-pulse delay-150" />
        </div>
      )}
    </div>
  );
}
