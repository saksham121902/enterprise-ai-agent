import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  GitBranch,
  Clock,
  CheckCircle2,
  AlertCircle,
  Loader2,
  ChevronRight,
  Zap,
  Bot,
  ArrowLeft,
} from 'lucide-react';
import { workflowApi } from '../lib/api';
import toast from 'react-hot-toast';
import './Workflows.css';

interface WorkflowSummary {
  id: string;
  name: string;
  status: string;
  total_steps: number;
  completed_steps: number;
  total_duration_ms: number;
  created_at: string;
}

interface WorkflowStep {
  step_order: number;
  agent_type: string;
  status: string;
  input_data: string | null;
  output_summary: string | null;
  error_message: string | null;
  duration_ms: number;
  model: string | null;
  input_tokens: number;
  output_tokens: number;
}

interface WorkflowDetail extends WorkflowSummary {
  description: string | null;
  total_tokens: number;
  trigger_message: string | null;
  final_output: string | null;
  error_message: string | null;
  steps: WorkflowStep[];
}

export function WorkflowsPage() {
  const [workflows, setWorkflows] = useState<WorkflowSummary[]>([]);
  const [selectedWorkflow, setSelectedWorkflow] = useState<WorkflowDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [_detailLoading, setDetailLoading] = useState(false);

  useEffect(() => {
    loadWorkflows();
  }, []);

  const loadWorkflows = async () => {
    try {
      const { data } = await workflowApi.list();
      setWorkflows(data);
    } catch {
      setWorkflows([]);
    } finally {
      setLoading(false);
    }
  };

  const loadWorkflowDetail = async (workflowId: string) => {
    setDetailLoading(true);
    try {
      const { data } = await workflowApi.get(workflowId);
      setSelectedWorkflow(data);
    } catch {
      toast.error('Failed to load workflow details');
    } finally {
      setDetailLoading(false);
    }
  };

  const statusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle2 size={16} className="status-completed" />;
      case 'running':
        return <Loader2 size={16} className="spinning status-processing" />;
      case 'failed':
        return <AlertCircle size={16} className="status-failed" />;
      default:
        return <Clock size={16} className="status-pending" />;
    }
  };

  const statusBadge = (status: string) => {
    const cls = status === 'completed' ? 'success' : status === 'failed' ? 'error' : status === 'running' ? 'info' : 'neutral';
    return <span className={`badge badge-${cls}`}>{status}</span>;
  };

  const formatDuration = (ms: number) => {
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
  };

  // Detail view
  if (selectedWorkflow) {
    return (
      <div className="page-content">
        <div className="dashboard-header">
          <div>
            <button
              className="btn btn-ghost btn-sm"
              onClick={() => setSelectedWorkflow(null)}
              style={{ marginBottom: 'var(--space-sm)' }}
            >
              <ArrowLeft size={16} /> Back to Workflows
            </button>
            <h1>{selectedWorkflow.name}</h1>
            <p className="text-secondary">{selectedWorkflow.description || selectedWorkflow.trigger_message}</p>
          </div>
          <div className="flex items-center gap-md">
            {statusBadge(selectedWorkflow.status)}
          </div>
        </div>

        {/* Summary stats */}
        <div className="workflow-stats">
          <div className="workflow-stat">
            <span className="stat-number">{selectedWorkflow.completed_steps}/{selectedWorkflow.total_steps}</span>
            <span className="stat-desc">Steps</span>
          </div>
          <div className="workflow-stat">
            <span className="stat-number">{formatDuration(selectedWorkflow.total_duration_ms)}</span>
            <span className="stat-desc">Duration</span>
          </div>
          <div className="workflow-stat">
            <span className="stat-number">{selectedWorkflow.total_tokens.toLocaleString()}</span>
            <span className="stat-desc">Tokens</span>
          </div>
        </div>

        {/* Steps */}
        <div className="dashboard-section">
          <h3>Execution Steps</h3>
          <div className="workflow-steps">
            {selectedWorkflow.steps.map((step, i) => (
              <motion.div
                key={i}
                className="workflow-step-card glass-card"
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.08 }}
              >
                <div className="step-number">{step.step_order}</div>
                <div className="step-body">
                  <div className="step-top">
                    <span className="badge badge-info">{step.agent_type}</span>
                    {statusBadge(step.status)}
                    {step.duration_ms > 0 && (
                      <span className="text-xs text-tertiary font-mono">{formatDuration(step.duration_ms)}</span>
                    )}
                    {step.model && (
                      <span className="text-xs text-tertiary"><Zap size={10} /> {step.model}</span>
                    )}
                  </div>
                  {step.output_summary && (
                    <p className="step-summary">{step.output_summary}</p>
                  )}
                  {step.error_message && (
                    <p className="step-error">{step.error_message}</p>
                  )}
                </div>
              </motion.div>
            ))}
          </div>
        </div>

        {/* Final output */}
        {selectedWorkflow.final_output && (
          <div className="dashboard-section">
            <h3>Final Output</h3>
            <div className="glass-card" style={{ padding: 'var(--space-lg)' }}>
              <p style={{ whiteSpace: 'pre-wrap', fontSize: 'var(--font-size-sm)', lineHeight: 1.7 }}>
                {selectedWorkflow.final_output}
              </p>
            </div>
          </div>
        )}
      </div>
    );
  }

  // List view
  return (
    <div className="page-content">
      <div className="dashboard-header">
        <div>
          <h1>Workflows</h1>
          <p className="text-secondary">Multi-step AI workflow executions</p>
        </div>
      </div>

      <div className="workflow-list">
        <AnimatePresence>
          {workflows.map((wf, i) => (
            <motion.div
              key={wf.id}
              className="workflow-item glass-card"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05 }}
              onClick={() => loadWorkflowDetail(wf.id)}
            >
              <div className="workflow-icon">
                <GitBranch size={24} />
              </div>
              <div className="workflow-info">
                <h4 className="workflow-name">{wf.name}</h4>
                <div className="workflow-meta">
                  <span><Bot size={12} /> {wf.total_steps} steps</span>
                  <span><Clock size={12} /> {formatDuration(wf.total_duration_ms)}</span>
                  <span>{new Date(wf.created_at).toLocaleDateString()}</span>
                </div>
              </div>
              <div className="flex items-center gap-sm">
                {statusIcon(wf.status)}
                {statusBadge(wf.status)}
              </div>
              <ChevronRight size={16} className="text-tertiary" />
            </motion.div>
          ))}
        </AnimatePresence>

        {!loading && workflows.length === 0 && (
          <div className="empty-state">
            <GitBranch size={48} strokeWidth={1} />
            <h3>No workflows yet</h3>
            <p className="text-secondary">
              Workflows are created automatically when the AI agent processes complex multi-step requests.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
