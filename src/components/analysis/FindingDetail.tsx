'use client';

import React from 'react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import type { Finding, FindingExplanation } from '@/types/analysis';

interface FindingDetailProps {
  finding: Finding;
  explanation: FindingExplanation | null;
  onExplain: (index: number) => void;
  onClose: () => void;
}

function severityBadgeClass(severity: string): string {
  switch (severity) {
    case 'error':
      return 'severity-badge severity-badge-error';
    case 'warning':
      return 'severity-badge severity-badge-warning';
    default:
      return 'severity-badge severity-badge-note';
  }
}

export default function FindingDetail({
  finding,
  explanation,
  onExplain,
  onClose,
}: FindingDetailProps) {
  // Infer language from file extension for syntax highlighting
  const ext = finding.file.split('.').pop() || '';
  const langMap: Record<string, string> = {
    py: 'python',
    js: 'javascript',
    ts: 'typescript',
    tsx: 'tsx',
    jsx: 'jsx',
    go: 'go',
    rs: 'rust',
    java: 'java',
    rb: 'ruby',
    php: 'php',
    c: 'c',
    cpp: 'cpp',
    h: 'c',
    yml: 'yaml',
    yaml: 'yaml',
    json: 'json',
    toml: 'toml',
    sh: 'bash',
    bash: 'bash',
  };
  const lang = langMap[ext] || 'text';

  return (
    <div className="border border-[var(--border-color)] rounded-lg bg-[var(--background)]/50 p-5 space-y-4">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-2 flex-wrap">
            <span className={severityBadgeClass(finding.severity)}>
              {finding.severity}
            </span>
            <span className="text-xs text-[var(--muted)] font-mono">
              {finding.ruleId}
            </span>
            <span className="text-xs text-[var(--muted)]">via {finding.tool}</span>
          </div>
          <p className="text-sm text-[var(--foreground)]">{finding.message}</p>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="text-[var(--muted)] hover:text-[var(--foreground)] transition-colors text-lg"
          aria-label="Close detail"
        >
          x
        </button>
      </div>

      {/* Location */}
      <div className="text-xs font-mono text-[var(--muted)]">
        {finding.file}:{finding.startLine}
        {finding.endLine > finding.startLine && `-${finding.endLine}`}
      </div>

      {/* Code snippet */}
      {finding.snippet && (
        <div className="rounded-md overflow-hidden border border-[var(--border-color)]">
          <SyntaxHighlighter
            language={lang}
            style={oneDark}
            showLineNumbers
            startingLineNumber={finding.startLine}
            customStyle={{
              margin: 0,
              fontSize: '0.75rem',
              borderRadius: '0.375rem',
            }}
          >
            {finding.snippet}
          </SyntaxHighlighter>
        </div>
      )}

      {/* CWE IDs */}
      {finding.cweIds && finding.cweIds.length > 0 && (
        <div className="flex gap-2 flex-wrap">
          {finding.cweIds.map((cwe) => (
            <a
              key={cwe}
              href={`https://cwe.mitre.org/data/definitions/${cwe.replace('CWE-', '')}.html`}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-[var(--link-color)] hover:text-[var(--highlight)] underline"
            >
              {cwe}
            </a>
          ))}
        </div>
      )}

      {/* Explanation */}
      {explanation ? (
        <div className="border-t border-[var(--border-color)] pt-4 space-y-2">
          <h4 className="text-sm font-semibold text-[var(--foreground)] font-serif">
            Explanation
          </h4>
          <p className="text-sm text-[var(--foreground)]">{explanation.explanation}</p>
          {explanation.remediation && (
            <>
              <h4 className="text-sm font-semibold text-[var(--foreground)] font-serif mt-3">
                Remediation
              </h4>
              <p className="text-sm text-[var(--foreground)]">{explanation.remediation}</p>
            </>
          )}
          {explanation.references && explanation.references.length > 0 && (
            <div className="flex flex-col gap-1 mt-2">
              {explanation.references.map((ref, i) => (
                <a
                  key={i}
                  href={ref}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-[var(--link-color)] hover:text-[var(--highlight)] truncate"
                >
                  {ref}
                </a>
              ))}
            </div>
          )}
        </div>
      ) : (
        <button
          type="button"
          onClick={() => onExplain(finding.index)}
          className="btn-japanese text-xs"
        >
          Explain this finding
        </button>
      )}
    </div>
  );
}
