'use client';

import React, { useMemo } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { FaHome } from 'react-icons/fa';
import ThemeToggle from '@/components/theme-toggle';
import AnalysisReport from '@/components/analysis/AnalysisReport';

export default function RepoAnalysisPage() {
  const params = useParams();
  const owner = params.owner as string;
  const repo = params.repo as string;

  // Construct a target path from the repo URL. The backend resolves
  // GitHub-style owner/repo to a cloned local directory.
  const targetPath = useMemo(() => `${owner}/${repo}`, [owner, repo]);

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
            <Link
              href={`/${owner}/${repo}`}
              className="text-sm text-[var(--accent-primary)] hover:text-[var(--highlight)] transition-colors"
            >
              {owner}/{repo}
            </Link>
            <span className="text-[var(--muted)]">/</span>
            <span className="text-sm text-[var(--foreground)] font-serif">
              Analysis
            </span>
          </div>
          <ThemeToggle />
        </div>
      </header>

      <main className="max-w-[90%] xl:max-w-[1400px] mx-auto">
        <AnalysisReport targetPath={targetPath} />
      </main>
    </div>
  );
}
