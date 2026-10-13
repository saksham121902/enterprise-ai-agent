import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { DollarSign, TrendingUp, BarChart3, PieChart } from 'lucide-react';
import { analyticsApi } from '../lib/api';
import './Analytics.css';

interface CostBreakdown {
  provider: string;
  model: string;
  requests: number;
  input_tokens: number;
  output_tokens: number;
  total_cost_usd: number;
}

export function AnalyticsPage() {
  const [costBreakdown, setCostBreakdown] = useState<CostBreakdown[]>([]);
  const [_loading, setLoading] = useState(true);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const { data } = await analyticsApi.costBreakdown();
      setCostBreakdown(data);
    } catch {
      setCostBreakdown([]);
    } finally {
      setLoading(false);
    }
  };

  const totalCost = costBreakdown.reduce((sum, r) => sum + r.total_cost_usd, 0);
  const totalRequests = costBreakdown.reduce((sum, r) => sum + r.requests, 0);
  const totalTokens = costBreakdown.reduce(
    (sum, r) => sum + r.input_tokens + r.output_tokens,
    0
  );

  return (
    <div className="page-content">
      <div className="dashboard-header">
        <div>
          <h1>Analytics & Cost Dashboard</h1>
          <p className="text-secondary">Monitor AI usage, costs, and performance metrics</p>
        </div>
      </div>

      {/* Summary stats */}
      <div className="stats-grid" style={{ marginBottom: 'var(--space-2xl)' }}>
        <motion.div
          className="stat-card glass-card"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <div className="stat-icon" style={{ background: 'linear-gradient(135deg, #f59e0b, #d97706)' }}>
            <DollarSign size={20} />
          </div>
          <div className="stat-info">
            <span className="stat-value">${totalCost.toFixed(4)}</span>
            <span className="stat-label">Total Cost</span>
          </div>
        </motion.div>

        <motion.div
          className="stat-card glass-card"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
        >
          <div className="stat-icon" style={{ background: 'linear-gradient(135deg, #7c3aed, #6366f1)' }}>
            <BarChart3 size={20} />
          </div>
          <div className="stat-info">
            <span className="stat-value">{totalRequests.toLocaleString()}</span>
            <span className="stat-label">API Requests</span>
          </div>
        </motion.div>

        <motion.div
          className="stat-card glass-card"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
        >
          <div className="stat-icon" style={{ background: 'linear-gradient(135deg, #10b981, #059669)' }}>
            <TrendingUp size={20} />
          </div>
          <div className="stat-info">
            <span className="stat-value">{(totalTokens / 1000).toFixed(1)}K</span>
            <span className="stat-label">Total Tokens</span>
          </div>
        </motion.div>
      </div>

      {/* Cost breakdown table */}
      <div className="dashboard-section">
        <h3>Cost Breakdown by Model</h3>
        {costBreakdown.length > 0 ? (
          <div className="table-container glass-card">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Provider</th>
                  <th>Model</th>
                  <th>Requests</th>
                  <th>Input Tokens</th>
                  <th>Output Tokens</th>
                  <th>Cost (USD)</th>
                </tr>
              </thead>
              <tbody>
                {costBreakdown.map((row, i) => (
                  <motion.tr
                    key={`${row.provider}-${row.model}`}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: i * 0.05 }}
                  >
                    <td>
                      <span className="badge badge-info">{row.provider}</span>
                    </td>
                    <td className="font-mono">{row.model}</td>
                    <td>{row.requests.toLocaleString()}</td>
                    <td>{row.input_tokens.toLocaleString()}</td>
                    <td>{row.output_tokens.toLocaleString()}</td>
                    <td className="cost-cell">${row.total_cost_usd.toFixed(4)}</td>
                  </motion.tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="empty-state">
            <PieChart size={48} strokeWidth={1} />
            <h3>No cost data yet</h3>
            <p className="text-secondary">Start using the AI agent to see cost analytics here</p>
          </div>
        )}
      </div>
    </div>
  );
}
