'use client';

import React from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { FaHome } from 'react-icons/fa';
import ThemeToggle from '@/components/theme-toggle';
import AnalysisReport from '@/components/analysis/AnalysisReport';

export default function AnalysisRunPage() {
  const params = useParams();
  const runId = params.runId as string;

  return (
    <div className="min-h-screen paper-texture p-4 md:p-8">
      <header className="max-w-[90%] xl:max-w-[1400px] mx-auto mb-8">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link
              href="/"
              className="text-[var(--accent-primary)] hover:text-[var(--highlight)] flex items-center gap-1.5 transition-colors border-b border-[var(--border-color)] hover:border-[var(--accent-primary)] pb-0.5"
            >
              <FaHome /> Home
            </Link>
            <span className="text-[var(--muted)]">/</span>
            <span className="text-sm text-[var(--foreground)] font-serif">
              Analysis Report
            </span>
          </div>
          <ThemeToggle />
        </div>
      </header>

      <main className="max-w-[90%] xl:max-w-[1400px] mx-auto">
        <AnalysisReport runId={runId} />
      </main>
    </div>
  );
}
