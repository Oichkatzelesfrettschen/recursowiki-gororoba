/** SARIF-aligned types for the analysis pipeline results. */

export type Severity = 'error' | 'warning' | 'note';

export interface Finding {
  index: number;
  tool: string;
  ruleId: string;
  message: string;
  severity: Severity;
  file: string;
  startLine: number;
  endLine: number;
  snippet?: string;
  cweIds?: string[];
  fingerprint?: string;
}

export interface FindingsResponse {
  run_id: string;
  total: number;
  findings: Finding[];
}

export interface AnalysisMetrics {
  run_id: string;
  total_findings: number;
  by_severity: Record<Severity, number>;
  by_tool: Record<string, number>;
  files_affected: number;
  tools_run: number;
  tools_succeeded: number;
  tools_failed: number;
  duration_seconds: number;
}

export interface TopologyNode {
  id: string;
  label: string;
  type: string;
  language?: string;
  size?: number;
}

export interface TopologyEdge {
  source: string;
  target: string;
  label?: string;
}

export interface TopologyGraph {
  nodes: TopologyNode[];
  edges: TopologyEdge[];
}

export type AnalysisPhase =
  | 'queued'
  | 'detecting'
  | 'provisioning'
  | 'running_tools'
  | 'normalizing'
  | 'merging'
  | 'agents'
  | 'complete'
  | 'failed';

export interface AnalysisStatus {
  run_id: string;
  status: AnalysisPhase;
  progress: number;
  message?: string;
  error?: string;
}

export interface SarifRule {
  id: string;
  shortDescription?: { text: string };
  fullDescription?: { text: string };
  helpUri?: string;
}

export interface SarifResult {
  ruleId: string;
  message: { text: string };
  level: string;
  locations?: Array<{
    physicalLocation?: {
      artifactLocation?: { uri: string };
      region?: {
        startLine?: number;
        endLine?: number;
        snippet?: { text: string };
      };
    };
  }>;
  fingerprints?: Record<string, string>;
}

export interface SarifRun {
  tool: {
    driver: {
      name: string;
      version?: string;
      rules?: SarifRule[];
    };
  };
  results: SarifResult[];
}

export interface SarifLog {
  $schema?: string;
  version: string;
  runs: SarifRun[];
}

export interface FindingExplanation {
  finding_index: number;
  explanation: string;
  remediation?: string;
  references?: string[];
}
