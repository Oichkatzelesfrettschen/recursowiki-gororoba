'use client';

import React, { useMemo, useState } from 'react';
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getPaginationRowModel,
  createColumnHelper,
  flexRender,
  type SortingState,
} from '@tanstack/react-table';
import type { Finding, FindingExplanation } from '@/types/analysis';
import FindingDetail from './FindingDetail';

interface FindingsTableProps {
  findings: Finding[];
  explanation: FindingExplanation | null;
  onExplain: (index: number) => void;
}

const columnHelper = createColumnHelper<Finding>();

function SeverityCell({ value }: { value: string }) {
  const cls =
    value === 'error'
      ? 'severity-badge severity-badge-error'
      : value === 'warning'
        ? 'severity-badge severity-badge-warning'
        : 'severity-badge severity-badge-note';
  return <span className={cls}>{value}</span>;
}

export default function FindingsTable({
  findings,
  explanation,
  onExplain,
}: FindingsTableProps) {
  const [sorting, setSorting] = useState<SortingState>([
    { id: 'severity', desc: false },
  ]);
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);

  const columns = useMemo(
    () => [
      columnHelper.accessor('severity', {
        header: 'Severity',
        cell: (info) => <SeverityCell value={info.getValue()} />,
        sortingFn: (a, b) => {
          const order = { error: 0, warning: 1, note: 2 };
          return (
            (order[a.original.severity] ?? 3) -
            (order[b.original.severity] ?? 3)
          );
        },
      }),
      columnHelper.accessor('tool', {
        header: 'Tool',
        cell: (info) => (
          <span className="text-xs font-mono text-[var(--muted)]">
            {info.getValue()}
          </span>
        ),
      }),
      columnHelper.accessor('ruleId', {
        header: 'Rule',
        cell: (info) => (
          <span className="text-xs font-mono">{info.getValue()}</span>
        ),
      }),
      columnHelper.accessor('message', {
        header: 'Message',
        cell: (info) => (
          <span className="text-sm line-clamp-2">{info.getValue()}</span>
        ),
      }),
      columnHelper.accessor('file', {
        header: 'File',
        cell: (info) => (
          <span className="text-xs font-mono text-[var(--muted)] truncate max-w-[200px] block">
            {info.getValue()}:{info.row.original.startLine}
          </span>
        ),
      }),
    ],
    [],
  );

  const table = useReactTable({
    data: findings,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: { pagination: { pageSize: 20 } },
  });

  return (
    <div className="card-japanese rounded-lg overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-left">
          <thead>
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id} className="border-b border-[var(--border-color)]">
                {headerGroup.headers.map((header) => (
                  <th
                    key={header.id}
                    className="px-4 py-3 text-xs font-semibold text-[var(--muted)] uppercase tracking-wider cursor-pointer hover:text-[var(--foreground)] transition-colors select-none"
                    onClick={header.column.getToggleSortingHandler()}
                  >
                    <div className="flex items-center gap-1">
                      {flexRender(header.column.columnDef.header, header.getContext())}
                      {{
                        asc: ' ^',
                        desc: ' v',
                      }[header.column.getIsSorted() as string] ?? ''}
                    </div>
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map((row) => (
              <React.Fragment key={row.id}>
                <tr
                  className="border-b border-[var(--border-color)] hover:bg-[var(--accent-secondary)]/10 cursor-pointer transition-colors"
                  onClick={() =>
                    setExpandedIndex(
                      expandedIndex === row.original.index ? null : row.original.index,
                    )
                  }
                >
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id} className="px-4 py-3">
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
                {expandedIndex === row.original.index && (
                  <tr>
                    <td colSpan={columns.length} className="px-4 py-3">
                      <FindingDetail
                        finding={row.original}
                        explanation={
                          explanation?.finding_index === row.original.index
                            ? explanation
                            : null
                        }
                        onExplain={onExplain}
                        onClose={() => setExpandedIndex(null)}
                      />
                    </td>
                  </tr>
                )}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between px-4 py-3 border-t border-[var(--border-color)]">
        <span className="text-xs text-[var(--muted)]">
          {findings.length} finding{findings.length !== 1 ? 's' : ''}
        </span>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => table.previousPage()}
            disabled={!table.getCanPreviousPage()}
            className="text-xs text-[var(--accent-primary)] disabled:text-[var(--muted)] transition-colors"
          >
            Previous
          </button>
          <span className="text-xs text-[var(--muted)]">
            Page {table.getState().pagination.pageIndex + 1} of {table.getPageCount()}
          </span>
          <button
            type="button"
            onClick={() => table.nextPage()}
            disabled={!table.getCanNextPage()}
            className="text-xs text-[var(--accent-primary)] disabled:text-[var(--muted)] transition-colors"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}
