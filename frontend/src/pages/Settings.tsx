import { useState } from 'react';
import { motion } from 'framer-motion';
import {
  User,
  Shield,
  Key,
  Palette,
  Cpu,
  Eye,
  EyeOff,
  Check,
  Bot,
} from 'lucide-react';
import { useAuthStore } from '../stores';
import { authApi } from '../lib/api';
import toast from 'react-hot-toast';
import './Settings.css';

export function SettingsPage() {
  const [activeTab, setActiveTab] = useState('profile');

  const tabs = [
    { id: 'profile', label: 'Profile', icon: User },
    { id: 'security', label: 'Security', icon: Shield },
    { id: 'ai', label: 'AI Preferences', icon: Cpu },
    { id: 'appearance', label: 'Appearance', icon: Palette },
  ];

  return (
    <div className="page-content">
      <div className="dashboard-header">
        <div>
          <h1>Settings</h1>
          <p className="text-secondary">Manage your account and preferences</p>
        </div>
      </div>

      <div className="settings-layout">
        {/* Settings tabs */}
        <div className="settings-tabs">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              className={`settings-tab ${activeTab === tab.id ? 'active' : ''}`}
              onClick={() => setActiveTab(tab.id)}
            >
              <tab.icon size={18} />
              <span>{tab.label}</span>
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div className="settings-content">
          {activeTab === 'profile' && <ProfileTab />}
          {activeTab === 'security' && <SecurityTab />}
          {activeTab === 'ai' && <AITab />}
          {activeTab === 'appearance' && <AppearanceTab />}
        </div>
      </div>
    </div>
  );
}

function ProfileTab() {
  const { user } = useAuthStore();

  if (!user) return null;

  return (
    <motion.div
      className="settings-panel"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
    >
      <h3>Profile Information</h3>
      <p className="text-secondary text-sm" style={{ marginBottom: 'var(--space-xl)' }}>
        Your account details and role information
      </p>

      <div className="profile-card glass-card">
        <div className="profile-avatar">
          {user.full_name.charAt(0).toUpperCase()}
        </div>
        <div className="profile-details">
          <div className="profile-field">
            <label>Full Name</label>
            <span>{user.full_name}</span>
          </div>
          <div className="profile-field">
            <label>Email</label>
            <span>{user.email}</span>
          </div>
          <div className="profile-field">
            <label>Username</label>
            <span>@{user.username}</span>
          </div>
          <div className="profile-field">
            <label>Role</label>
            <span className="badge badge-info">{user.role_name || 'User'}</span>
          </div>
          <div className="profile-field">
            <label>Status</label>
            <span className={`badge ${user.is_active ? 'badge-success' : 'badge-error'}`}>
              {user.is_active ? 'Active' : 'Inactive'}
            </span>
          </div>
          <div className="profile-field">
            <label>Verified</label>
            <span className={`badge ${user.is_verified ? 'badge-success' : 'badge-warning'}`}>
              {user.is_verified ? 'Verified' : 'Unverified'}
            </span>
          </div>
        </div>
      </div>
    </motion.div>
  );
}

function SecurityTab() {
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPasswords, setShowPasswords] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();

    if (newPassword !== confirmPassword) {
      toast.error('New passwords do not match');
      return;
    }

    if (newPassword.length < 8) {
      toast.error('Password must be at least 8 characters');
      return;
    }

    setLoading(true);
    try {
      await authApi.changePassword({
        current_password: currentPassword,
        new_password: newPassword,
      });
      toast.success('Password changed successfully');
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (err: any) {
      toast.error(err.response?.data?.error?.message || 'Failed to change password');
    } finally {
      setLoading(false);
    }
  };

  return (
    <motion.div
      className="settings-panel"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
    >
      <h3>Security</h3>
      <p className="text-secondary text-sm" style={{ marginBottom: 'var(--space-xl)' }}>
        Update your password and security settings
      </p>

      <form onSubmit={handleChangePassword} className="settings-form glass-card">
        <h4><Key size={16} /> Change Password</h4>

        <div className="form-group">
          <label htmlFor="current-pw">Current Password</label>
          <div className="password-field">
            <input
              id="current-pw"
              type={showPasswords ? 'text' : 'password'}
              className="input"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              required
            />
          </div>
        </div>

        <div className="form-group">
          <label htmlFor="new-pw">New Password</label>
          <div className="password-field">
            <input
              id="new-pw"
              type={showPasswords ? 'text' : 'password'}
              className="input"
              placeholder="Min. 8 characters"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              required
              minLength={8}
            />
          </div>
        </div>

        <div className="form-group">
          <label htmlFor="confirm-pw">Confirm New Password</label>
          <div className="password-field">
            <input
              id="confirm-pw"
              type={showPasswords ? 'text' : 'password'}
              className="input"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
              minLength={8}
            />
          </div>
        </div>

        <div className="form-actions">
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={() => setShowPasswords(!showPasswords)}
          >
            {showPasswords ? <EyeOff size={14} /> : <Eye size={14} />}
            {showPasswords ? 'Hide' : 'Show'} passwords
          </button>
          <button type="submit" className="btn btn-primary" disabled={loading}>
            {loading ? <div className="spinner" /> : <><Check size={16} /> Update Password</>}
          </button>
        </div>
      </form>
    </motion.div>
  );
}

function AITab() {
  const providers = [
    { name: 'OpenAI', model: 'gpt-4o', status: 'primary', color: '#10b981' },
    { name: 'Anthropic', model: 'claude-sonnet-4-20250514', status: 'fallback', color: '#f59e0b' },
    { name: 'Google', model: 'gemini-2.0-flash', status: 'fallback', color: '#3b82f6' },
    { name: 'Ollama', model: 'llama3.1', status: 'local', color: '#a855f7' },
  ];

  return (
    <motion.div
      className="settings-panel"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
    >
      <h3>AI Preferences</h3>
      <p className="text-secondary text-sm" style={{ marginBottom: 'var(--space-xl)' }}>
        View configured LLM providers and model settings
      </p>

      <div className="provider-grid">
        {providers.map((p, i) => (
          <motion.div
            key={p.name}
            className="provider-card glass-card"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.08 }}
          >
            <div className="provider-header">
              <div className="provider-icon" style={{ background: p.color + '20', color: p.color }}>
                <Bot size={20} />
              </div>
              <div>
                <h4>{p.name}</h4>
                <span className="text-xs font-mono text-secondary">{p.model}</span>
              </div>
            </div>
            <span className={`badge ${p.status === 'primary' ? 'badge-success' : p.status === 'fallback' ? 'badge-warning' : 'badge-neutral'}`}>
              {p.status}
            </span>
          </motion.div>
        ))}
      </div>

      <div className="settings-note glass-card">
        <Cpu size={16} />
        <p className="text-sm text-secondary">
          LLM provider configuration is managed via environment variables. The primary provider is used first,
          with automatic fallback to secondary providers if the primary fails.
        </p>
      </div>
    </motion.div>
  );
}

function AppearanceTab() {
  return (
    <motion.div
      className="settings-panel"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
    >
      <h3>Appearance</h3>
      <p className="text-secondary text-sm" style={{ marginBottom: 'var(--space-xl)' }}>
        Customize the look and feel of your workspace
      </p>

      <div className="appearance-options glass-card">
        <div className="appearance-option active">
          <div className="theme-preview dark">
            <div className="tp-sidebar" />
            <div className="tp-main">
              <div className="tp-line" />
              <div className="tp-line short" />
            </div>
          </div>
          <span>Dark Mode</span>
          <Check size={16} className="check-icon" />
        </div>
        <div className="appearance-option disabled">
          <div className="theme-preview light">
            <div className="tp-sidebar" />
            <div className="tp-main">
              <div className="tp-line" />
              <div className="tp-line short" />
            </div>
          </div>
          <span>Light Mode</span>
          <span className="badge badge-neutral">Soon</span>
        </div>
      </div>
    </motion.div>
  );
}
