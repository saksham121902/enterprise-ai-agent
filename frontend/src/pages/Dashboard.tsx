import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import {
  MessageSquare,
  FileText,
  DollarSign,
  Zap,
  TrendingUp,
  ArrowUpRight,
  Bot,
} from 'lucide-react';
import { analyticsApi } from '../lib/api';
import './Dashboard.css';

interface OverviewData {
  total_messages: number;
  total_documents: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_cost_usd: number;
  top_tools: { name: string; count: number }[];
}

export function DashboardPage() {
  const [overview, setOverview] = useState<OverviewData | null>(null);
  const [_loading, setLoading] = useState(true);

  useEffect(() => {
    loadOverview();
  }, []);

  const loadOverview = async () => {
    try {
      const { data } = await analyticsApi.overview();
      setOverview(data);
    } catch {
      // Use placeholder data when API is unavailable
      setOverview({
        total_messages: 0,
        total_documents: 0,
        total_input_tokens: 0,
        total_output_tokens: 0,
        total_cost_usd: 0,
        top_tools: [],
      });
    } finally {
      setLoading(false);
    }
  };

  const stats = overview
    ? [
        {
          label: 'Total Messages',
          value: overview.total_messages.toLocaleString(),
          icon: MessageSquare,
          color: '#7c3aed',
          gradient: 'linear-gradient(135deg, #7c3aed, #6366f1)',
        },
        {
          label: 'Documents',
          value: overview.total_documents.toLocaleString(),
          icon: FileText,
          color: '#3b82f6',
          gradient: 'linear-gradient(135deg, #3b82f6, #2563eb)',
        },
        {
          label: 'Total Tokens',
          value: (
            (overview.total_input_tokens + overview.total_output_tokens) /
            1000
          ).toFixed(1) + 'K',
          icon: Zap,
          color: '#10b981',
          gradient: 'linear-gradient(135deg, #10b981, #059669)',
        },
        {
          label: 'Total Cost',
          value: '$' + overview.total_cost_usd.toFixed(2),
          icon: DollarSign,
          color: '#f59e0b',
          gradient: 'linear-gradient(135deg, #f59e0b, #d97706)',
        },
      ]
    : [];

  return (
    <div className="page-content">
      <div className="dashboard-header">
        <div>
          <h1>Dashboard</h1>
          <p className="text-secondary">Overview of your Enterprise AI Agent</p>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="stats-grid">
        {stats.map((stat, i) => (
          <motion.div
            key={stat.label}
            className="stat-card glass-card"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.1 }}
          >
            <div className="stat-icon" style={{ background: stat.gradient }}>
              <stat.icon size={20} />
            </div>
            <div className="stat-info">
              <span className="stat-value">{stat.value}</span>
              <span className="stat-label">{stat.label}</span>
            </div>
            <div className="stat-trend">
              <TrendingUp size={14} />
              <ArrowUpRight size={14} />
            </div>
          </motion.div>
        ))}
      </div>

      {/* Quick Actions */}
      <div className="dashboard-section">
        <h3>Quick Actions</h3>
        <div className="quick-actions">
          {[
            { label: 'New Chat', href: '/chat', icon: MessageSquare, color: '#7c3aed' },
            { label: 'Upload Document', href: '/documents', icon: FileText, color: '#3b82f6' },
            { label: 'View Analytics', href: '/analytics', icon: TrendingUp, color: '#10b981' },
            { label: 'Workflows', href: '/workflows', icon: Zap, color: '#f59e0b' },
          ].map((action, i) => (
            <motion.a
              key={action.label}
              href={action.href}
              className="action-card glass-card"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.4 + i * 0.1 }}
              whileHover={{ y: -4 }}
            >
              <div className="action-icon" style={{ background: action.color + '20', color: action.color }}>
                <action.icon size={24} />
              </div>
              <span className="action-label">{action.label}</span>
            </motion.a>
          ))}
        </div>
      </div>

      {/* AI Capabilities */}
      <div className="dashboard-section">
        <h3>AI Agent Capabilities</h3>
        <div className="capabilities-grid">
          {[
            { title: 'Document Q&A', desc: 'Ask questions about uploaded contracts, reports, and documents' },
            { title: 'SQL Queries', desc: 'Query your databases using natural language' },
            { title: 'Multi-Agent Workflows', desc: 'Complex multi-step tasks with specialized AI agents' },
            { title: 'Tool Execution', desc: 'Calculator, date/time, text processing, and more' },
            { title: 'Long-Term Memory', desc: 'Remembers your preferences and important context' },
            { title: 'Cost Tracking', desc: 'Monitor AI usage and costs in real-time' },
          ].map((cap, i) => (
            <motion.div
              key={cap.title}
              className="capability-card"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.6 + i * 0.05 }}
            >
              <Bot size={20} className="cap-icon" />
              <div>
                <h4>{cap.title}</h4>
                <p className="text-secondary text-sm">{cap.desc}</p>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </div>
  );
}
