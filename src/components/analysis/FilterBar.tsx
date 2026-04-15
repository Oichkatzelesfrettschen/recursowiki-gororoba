'use client';

import React from 'react';
import type { Severity } from '@/types/analysis';

interface FilterBarProps {
  tools: string[];
  selectedSeverity: Severity | '';
  selectedTool: string;
  fileFilter: string;
  onSeverityChange: (severity: Severity | '') => void;
  onToolChange: (tool: string) => void;
  onFileChange: (file: string) => void;
}

const SEVERITIES: Array<{ value: Severity | ''; label: string }> = [
  { value: '', label: 'All Severities' },
  { value: 'error', label: 'Error' },
  { value: 'warning', label: 'Warning' },
  { value: 'note', label: 'Note' },
];

export default function FilterBar({
  tools,
  selectedSeverity,
  selectedTool,
  fileFilter,
  onSeverityChange,
  onToolChange,
  onFileChange,
}: FilterBarProps) {
  return (
    <div className="flex flex-wrap gap-3 items-center p-4 card-japanese rounded-lg">
      <select
        value={selectedSeverity}
        onChange={(e) => onSeverityChange(e.target.value as Severity | '')}
        className="input-japanese text-sm"
      >
        {SEVERITIES.map((s) => (
          <option key={s.value} value={s.value}>
            {s.label}
          </option>
        ))}
      </select>

      <select
        value={selectedTool}
        onChange={(e) => onToolChange(e.target.value)}
        className="input-japanese text-sm"
      >
        <option value="">All Tools</option>
        {tools.map((t) => (
          <option key={t} value={t}>
            {t}
          </option>
        ))}
      </select>

      <input
        type="text"
        value={fileFilter}
        onChange={(e) => onFileChange(e.target.value)}
        placeholder="Filter by file path..."
        className="input-japanese text-sm flex-1 min-w-[200px]"
      />

      {(selectedSeverity || selectedTool || fileFilter) && (
        <button
          type="button"
          onClick={() => {
            onSeverityChange('');
            onToolChange('');
            onFileChange('');
          }}
          className="text-xs text-[var(--muted)] hover:text-[var(--highlight)] transition-colors"
        >
          Clear filters
        </button>
      )}
    </div>
  );
}
