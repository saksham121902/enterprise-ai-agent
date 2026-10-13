import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ShieldCheck,
  Clock,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Loader2,
  MessageSquare,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import { approvalApi } from '../lib/api';
import toast from 'react-hot-toast';
import './Approvals.css';

interface ApprovalEntry {
  id: string;
  operation_type: string;
  status: string;
  description: string;
  payload_json: string | null;
  reviewer_notes: string | null;
  requested_by: string;
  reviewed_by: string | null;
  created_at: string;
  updated_at: string;
}

const STATUS_TABS = [
  { key: '', label: 'All' },
  { key: 'pending', label: 'Pending' },
  { key: 'approved', label: 'Approved' },
  { key: 'rejected', label: 'Rejected' },
];

export function ApprovalsPage() {
  const [approvals, setApprovals] = useState<ApprovalEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('');
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [processingId, setProcessingId] = useState<string | null>(null);

  useEffect(() => {
    loadApprovals();
  }, [activeTab]);

  const loadApprovals = async () => {
    setLoading(true);
    try {
      const { data } = await approvalApi.list(activeTab || undefined);
      setApprovals(data);
    } catch {
      setApprovals([]);
    } finally {
      setLoading(false);
    }
  };

  const handleApprove = async (id: string) => {
    setProcessingId(id);
    try {
      await approvalApi.approve(id, notes[id]);
      toast.success('Request approved');
      loadApprovals();
    } catch (err: any) {
      toast.error(err.response?.data?.error?.message || 'Failed to approve');
    } finally {
      setProcessingId(null);
    }
  };

  const handleReject = async (id: string) => {
    setProcessingId(id);
    try {
      await approvalApi.reject(id, notes[id]);
      toast.success('Request rejected');
      loadApprovals();
    } catch (err: any) {
      toast.error(err.response?.data?.error?.message || 'Failed to reject');
    } finally {
      setProcessingId(null);
    }
  };

  const statusIcon = (status: string) => {
    switch (status) {
      case 'approved':
        return <CheckCircle2 size={16} className="status-completed" />;
      case 'rejected':
        return <XCircle size={16} className="status-failed" />;
      default:
        return <Clock size={16} className="status-pending" />;
    }
  };

  const statusBadgeClass = (status: string) => {
    switch (status) {
      case 'approved': return 'badge-success';
      case 'rejected': return 'badge-error';
      default: return 'badge-warning';
    }
  };

  const pendingCount = approvals.filter((a) => a.status === 'pending').length;

  return (
    <div className="page-content">
      <div className="dashboard-header">
        <div>
          <h1>Approvals</h1>
          <p className="text-secondary">
            Review and manage human approval requests for sensitive AI operations
          </p>
        </div>
        {pendingCount > 0 && (
          <div className="pending-badge">
            <AlertTriangle size={16} />
            <span>{pendingCount} pending</span>
          </div>
        )}
      </div>

      {/* Status filter tabs */}
      <div className="approval-tabs">
        {STATUS_TABS.map((tab) => (
          <button
            key={tab.key}
            className={`approval-tab ${activeTab === tab.key ? 'active' : ''}`}
            onClick={() => setActiveTab(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Approvals list */}
      <div className="approvals-list">
        <AnimatePresence>
          {approvals.map((approval, i) => {
            const isExpanded = expandedId === approval.id;
            const isPending = approval.status === 'pending';
            const isProcessing = processingId === approval.id;

            return (
              <motion.div
                key={approval.id}
                className={`approval-card glass-card ${isPending ? 'pending' : ''}`}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, x: -20 }}
                transition={{ delay: i * 0.05 }}
              >
                <div
                  className="approval-summary"
                  onClick={() => setExpandedId(isExpanded ? null : approval.id)}
                >
                  <div className="approval-icon">
                    {statusIcon(approval.status)}
                  </div>
                  <div className="approval-info">
                    <div className="approval-top">
                      <span className="badge badge-info">{approval.operation_type}</span>
                      <span className={`badge ${statusBadgeClass(approval.status)}`}>
                        {approval.status}
                      </span>
                    </div>
                    <p className="approval-desc">{approval.description}</p>
                    <div className="approval-meta">
                      <span className="text-xs text-tertiary">
                        <Clock size={10} /> {new Date(approval.created_at).toLocaleString()}
                      </span>
                    </div>
                  </div>
                  <div className="approval-toggle">
                    {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                  </div>
                </div>

                <AnimatePresence>
                  {isExpanded && (
                    <motion.div
                      className="approval-detail"
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: 'auto', opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.2 }}
                    >
                      {/* Payload */}
                      {approval.payload_json && (
                        <div className="approval-payload">
                          <h4>Operation Details</h4>
                          <pre className="payload-code">
                            {(() => {
                              try {
                                return JSON.stringify(JSON.parse(approval.payload_json), null, 2);
                              } catch {
                                return approval.payload_json;
                              }
                            })()}
                          </pre>
                        </div>
                      )}

                      {/* Reviewer notes (if already reviewed) */}
                      {approval.reviewer_notes && (
                        <div className="reviewer-notes">
                          <h4><MessageSquare size={14} /> Reviewer Notes</h4>
                          <p>{approval.reviewer_notes}</p>
                        </div>
                      )}

                      {/* Actions (only for pending) */}
                      {isPending && (
                        <div className="approval-actions">
                          <div className="notes-input-group">
                            <input
                              className="input"
                              placeholder="Add notes (optional)..."
                              value={notes[approval.id] || ''}
                              onChange={(e) =>
                                setNotes({ ...notes, [approval.id]: e.target.value })
                              }
                            />
                          </div>
                          <div className="action-buttons">
                            <button
                              className="btn btn-danger"
                              onClick={() => handleReject(approval.id)}
                              disabled={isProcessing}
                            >
                              {isProcessing ? (
                                <Loader2 size={16} className="spinning" />
                              ) : (
                                <XCircle size={16} />
                              )}
                              Reject
                            </button>
                            <button
                              className="btn btn-primary approve-btn"
                              onClick={() => handleApprove(approval.id)}
                              disabled={isProcessing}
                            >
                              {isProcessing ? (
                                <Loader2 size={16} className="spinning" />
                              ) : (
                                <CheckCircle2 size={16} />
                              )}
                              Approve
                            </button>
                          </div>
                        </div>
                      )}
                    </motion.div>
                  )}
                </AnimatePresence>
              </motion.div>
            );
          })}
        </AnimatePresence>

        {!loading && approvals.length === 0 && (
          <div className="empty-state">
            <ShieldCheck size={48} strokeWidth={1} />
            <h3>No approval requests</h3>
            <p className="text-secondary">
              {activeTab
                ? `No ${activeTab} requests found.`
                : 'Approval requests are created when the AI agent needs authorization for sensitive operations like SQL writes or external API calls.'}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
