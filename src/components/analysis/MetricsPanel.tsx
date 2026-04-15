'use client';

import React from 'react';
import type { AnalysisMetrics } from '@/types/analysis';

interface MetricsPanelProps {
  metrics: AnalysisMetrics;
}

interface MetricCardProps {
  label: string;
  value: string | number;
  subtitle?: string;
  accent?: boolean;
}

function MetricCard({ label, value, subtitle, accent }: MetricCardProps) {
  return (
    <div className="card-japanese p-4 rounded-lg text-center">
      <p className="text-xs text-[var(--muted)] uppercase tracking-wider mb-1">{label}</p>
      <p
        className={`text-2xl font-bold ${
          accent ? 'text-[var(--accent-primary)]' : 'text-[var(--foreground)]'
        }`}
      >
        {value}
      </p>
      {subtitle && <p className="text-xs text-[var(--muted)] mt-1">{subtitle}</p>}
    </div>
  );
}

export default function MetricsPanel({ metrics }: MetricsPanelProps) {
  const duration =
    metrics.duration_seconds < 60
      ? `${metrics.duration_seconds.toFixed(1)}s`
      : `${(metrics.duration_seconds / 60).toFixed(1)}m`;

  return (
    <div className="card-japanese p-6 rounded-lg">
      <h3 className="text-sm font-semibold text-[var(--foreground)] mb-4 font-serif">
        Analysis Metrics
      </h3>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <MetricCard label="Total Findings" value={metrics.total_findings} accent />
        <MetricCard label="Files Affected" value={metrics.files_affected} />
        <MetricCard
          label="Tools"
          value={`${metrics.tools_succeeded}/${metrics.tools_run}`}
          subtitle={metrics.tools_failed > 0 ? `${metrics.tools_failed} failed` : 'All passed'}
        />
        <MetricCard label="Duration" value={duration} />
      </div>
    </div>
  );
}
