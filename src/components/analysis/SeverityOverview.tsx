'use client';

import React from 'react';
import {
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import type { Severity } from '@/types/analysis';

interface SeverityOverviewProps {
  bySeverity: Record<Severity, number>;
  total: number;
}

const SEVERITY_COLORS: Record<Severity, string> = {
  error: 'var(--severity-error)',
  warning: 'var(--severity-warning)',
  note: 'var(--severity-note)',
};

const SEVERITY_LABELS: Record<Severity, string> = {
  error: 'Error',
  warning: 'Warning',
  note: 'Note',
};

export default function SeverityOverview({ bySeverity, total }: SeverityOverviewProps) {
  const pieData = (Object.keys(bySeverity) as Severity[])
    .filter((k) => bySeverity[k] > 0)
    .map((k) => ({
      name: SEVERITY_LABELS[k],
      value: bySeverity[k],
      color: SEVERITY_COLORS[k],
    }));

  const barData = (Object.keys(bySeverity) as Severity[]).map((k) => ({
    name: SEVERITY_LABELS[k],
    count: bySeverity[k],
    fill: SEVERITY_COLORS[k],
  }));

  return (
    <div className="card-japanese p-6 rounded-lg">
      <h3 className="text-sm font-semibold text-[var(--foreground)] mb-4 font-serif">
        Severity Distribution
      </h3>

      <div className="flex items-center gap-6">
        {/* Donut */}
        <div className="relative w-32 h-32 flex-shrink-0">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={pieData}
                innerRadius={30}
                outerRadius={55}
                paddingAngle={2}
                dataKey="value"
                stroke="none"
              >
                {pieData.map((entry, i) => (
                  <Cell key={i} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{
                  background: 'var(--card-bg)',
                  border: '1px solid var(--border-color)',
                  borderRadius: '0.5rem',
                  fontSize: '0.75rem',
                }}
              />
            </PieChart>
          </ResponsiveContainer>
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="text-lg font-bold text-[var(--foreground)]">{total}</span>
          </div>
        </div>

        {/* Bar chart */}
        <div className="flex-1 h-32">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={barData} layout="vertical">
              <XAxis type="number" hide />
              <YAxis
                type="category"
                dataKey="name"
                width={60}
                tick={{ fill: 'var(--foreground)', fontSize: 12 }}
              />
              <Tooltip
                contentStyle={{
                  background: 'var(--card-bg)',
                  border: '1px solid var(--border-color)',
                  borderRadius: '0.5rem',
                  fontSize: '0.75rem',
                }}
              />
              <Bar dataKey="count" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Legend */}
      <div className="flex gap-4 mt-4 justify-center">
        {pieData.map((entry) => (
          <div key={entry.name} className="flex items-center gap-1.5 text-xs">
            <div
              className="w-2.5 h-2.5 rounded-full"
              style={{ backgroundColor: entry.color }}
            />
            <span className="text-[var(--muted)]">{entry.name}</span>
            <span className="font-semibold text-[var(--foreground)]">{entry.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
