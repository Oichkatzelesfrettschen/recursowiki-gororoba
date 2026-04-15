'use client';

import React, { useMemo, useState } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import type { TopologyGraph } from '@/types/analysis';

interface DependencyGraphProps {
  topology: TopologyGraph;
}

const NODE_COLORS: Record<string, string> = {
  module: '#9b7cb9',
  package: '#e8927c',
  file: '#7c9b7c',
  class: '#7c7cb9',
  function: '#b9a07c',
};

export default function DependencyGraph({ topology }: DependencyGraphProps) {
  const [collapsed, setCollapsed] = useState(false);

  const initialNodes: Node[] = useMemo(
    () =>
      topology.nodes.map((n, i) => ({
        id: n.id,
        data: {
          label: (
            <div className="text-xs">
              <div className="font-semibold">{n.label}</div>
              {n.language && (
                <div className="text-[10px] opacity-70">{n.language}</div>
              )}
            </div>
          ),
        },
        position: {
          x: (i % 6) * 200 + Math.random() * 40,
          y: Math.floor(i / 6) * 120 + Math.random() * 40,
        },
        style: {
          background: NODE_COLORS[n.type] || '#9b7cb9',
          color: 'white',
          border: 'none',
          borderRadius: '0.5rem',
          padding: '8px 12px',
          fontSize: '12px',
        },
      })),
    [topology.nodes],
  );

  const initialEdges: Edge[] = useMemo(
    () =>
      topology.edges.map((e, i) => ({
        id: `e-${i}`,
        source: e.source,
        target: e.target,
        label: e.label,
        animated: true,
        style: { stroke: 'var(--border-color)' },
        labelStyle: { fontSize: 10, fill: 'var(--muted)' },
      })),
    [topology.edges],
  );

  const [nodes, , onNodesChange] = useNodesState(initialNodes);
  const [edges, , onEdgesChange] = useEdgesState(initialEdges);

  if (topology.nodes.length === 0) return null;

  return (
    <div className="card-japanese rounded-lg overflow-hidden">
      <button
        type="button"
        onClick={() => setCollapsed(!collapsed)}
        className="w-full flex items-center justify-between p-4 text-sm font-semibold text-[var(--foreground)] font-serif hover:bg-[var(--accent-secondary)]/10 transition-colors"
      >
        <span>Dependency Graph ({topology.nodes.length} nodes)</span>
        <span className="text-[var(--muted)]">{collapsed ? '+' : '-'}</span>
      </button>

      {!collapsed && (
        <div className="h-[500px] border-t border-[var(--border-color)]">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            fitView
            attributionPosition="bottom-left"
          >
            <Background gap={20} size={1} color="var(--border-color)" />
            <Controls
              style={{
                background: 'var(--card-bg)',
                border: '1px solid var(--border-color)',
                borderRadius: '0.5rem',
              }}
            />
            <MiniMap
              nodeColor={(n) => n.style?.background as string || '#9b7cb9'}
              maskColor="rgba(0,0,0,0.1)"
              style={{
                background: 'var(--card-bg)',
                border: '1px solid var(--border-color)',
                borderRadius: '0.5rem',
              }}
            />
          </ReactFlow>
        </div>
      )}
    </div>
  );
}
