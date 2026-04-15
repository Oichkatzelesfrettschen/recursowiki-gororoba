'use client';

import React from 'react';

interface ToolInfo {
  name: string;
  count: number;
  success: boolean;
  duration?: number;
}

interface ToolBreakdownProps {
  byTool: Record<string, number>;
  toolResults?: Record<string, { success: boolean; duration_seconds?: number }>;
}

export default function ToolBreakdown({ byTool, toolResults }: ToolBreakdownProps) {
  const tools: ToolInfo[] = Object.entries(byTool).map(([name, count]) => ({
    name,
    count,
    success: toolResults?.[name]?.success ?? true,
    duration: toolResults?.[name]?.duration_seconds,
  }));

  // Sort: most findings first
  tools.sort((a, b) => b.count - a.count);

  return (
    <div className="card-japanese p-6 rounded-lg">
      <h3 className="text-sm font-semibold text-[var(--foreground)] mb-4 font-serif">
        Tool Results
      </h3>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
        {tools.map((tool) => (
          <div
            key={tool.name}
            className="flex items-center gap-3 p-3 rounded-md border border-[var(--border-color)] bg-[var(--background)]/50"
          >
            <div
              className={`w-2 h-2 rounded-full flex-shrink-0 ${
                tool.success
                  ? 'bg-green-500'
                  : 'bg-[var(--severity-error)]'
              }`}
            />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-[var(--foreground)] truncate">
                {tool.name}
              </p>
              <p className="text-xs text-[var(--muted)]">
                {tool.count} finding{tool.count !== 1 ? 's' : ''}
                {tool.duration != null && ` -- ${tool.duration.toFixed(1)}s`}
              </p>
            </div>
            <span className="text-lg font-bold text-[var(--accent-primary)]">
              {tool.count}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
