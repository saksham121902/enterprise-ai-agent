import { useState, useEffect } from 'react';
import axios from 'axios';
import { Server, CheckCircle2, AlertCircle, RefreshCw, Settings, Database } from 'lucide-react';
import { getApiBaseUrl, getCleanBackendRoot, setCustomApiUrl } from '../lib/api';
import toast from 'react-hot-toast';
import './BackendStatus.css';

export function BackendStatusWidget() {
  const [cleanRoot, setCleanRoot] = useState(getCleanBackendRoot());
  const [status, setStatus] = useState<'idle' | 'checking' | 'waking' | 'online' | 'offline'>('idle');
  const [statusText, setStatusText] = useState<string>('');
  const [showConfig, setShowConfig] = useState(false);
  const [inputUrl, setInputUrl] = useState('');
  const [wakeCountdown, setWakeCountdown] = useState(0);
  const [seeding, setSeeding] = useState(false);

  // Check health on initial mount
  useEffect(() => {
    void checkHealth(false);
  }, []);

  const checkHealth = async (notify = true) => {
    setStatus('checking');
    setStatusText('Checking backend health...');
    const root = getCleanBackendRoot();
    try {
      const res = await axios.get(`${root}/health`, { timeout: 8000 });
      if (res.status === 200) {
        setStatus('online');
        setStatusText('Backend is Online & Healthy');
        if (notify) toast.success('Backend is online and ready!');
      } else {
        setStatus('offline');
        setStatusText(`Unexpected status (${res.status})`);
      }
    } catch (err: any) {
      setStatus('offline');
      if (err.code === 'ECONNABORTED' || err.message?.includes('timeout')) {
        setStatusText('Server timed out (likely sleeping or deploying)');
      } else {
        setStatusText('Cannot reach backend (sleeping or incorrect URL)');
      }
      if (notify) {
        toast.error('Could not reach backend. It may be asleep on Render free tier.');
      }
    }
  };

  const handleWakeUp = () => {
    setStatus('waking');
    const totalSeconds = 55;
    setWakeCountdown(totalSeconds);

    const root = getCleanBackendRoot();
    let secondsLeft = totalSeconds;

    const interval = window.setInterval(() => {
      void (async () => {
        secondsLeft -= 3;
        setWakeCountdown(Math.max(0, secondsLeft));

        try {
          const res = await axios.get(`${root}/health`, { timeout: 3500 });
          if (res.status === 200) {
            window.clearInterval(interval);
            setStatus('online');
            setStatusText('Backend is now awake and ready!');
            toast.success('Backend woke up successfully! You can now log in.');
            return;
          }
        } catch {
          // Keep waiting until countdown expires
        }

        if (secondsLeft <= 0) {
          window.clearInterval(interval);
          setStatus('offline');
          setStatusText('Wake-up timed out. Check Render dashboard logs.');
          toast.error('Backend did not respond in time. Please check your Render dashboard.');
        }
      })();
    }, 3000);
  };

  const handleSaveUrl = () => {
    if (!inputUrl.trim()) {
      setCustomApiUrl(null);
      toast.success('Reset backend URL to automatic detection');
    } else {
      let clean = inputUrl.trim().replace(/\/+$/, '');
      if (!clean.startsWith('http://') && !clean.startsWith('https://')) {
        clean = `https://${clean}`;
      }
      setCustomApiUrl(clean);
      toast.success('Custom backend URL saved!');
    }
    setCleanRoot(getCleanBackendRoot());
    setShowConfig(false);
    setTimeout(() => { void checkHealth(true); }, 200);
  };

  const handleSeedDatabase = async () => {
    setSeeding(true);
    const root = getCleanBackendRoot();
    try {
      const res = await axios.post(`${root}/seed`, {}, { timeout: 25000 });
      toast.success(res.data?.message || 'Database seeded successfully!');
      setStatus('online');
    } catch (err: any) {
      // Try GET if POST is not permitted
      try {
        const getRes = await axios.get(`${root}/seed`, { timeout: 25000 });
        toast.success(getRes.data?.message || 'Database seeded successfully!');
        setStatus('online');
      } catch (innerErr: any) {
        toast.error(innerErr.response?.data?.message || 'Seeding failed. Ensure backend is running.');
      }
    } finally {
      setSeeding(false);
    }
  };

  return (
    <div className="backend-widget">
      <div className="backend-status-row">
        <div className="status-indicator-group">
          <span className={`status-dot ${status}`} />
          <Server size={14} className="server-icon" />
          <span className="backend-url-display" title={cleanRoot}>
            {cleanRoot.replace(/^https?:\/\//, '')}
          </span>
        </div>

        <div className="widget-actions">
          {status === 'checking' ? (
            <span className="status-pill checking">
              <RefreshCw size={12} className="spinning" /> Checking...
            </span>
          ) : status === 'online' ? (
            <span className="status-pill online">
              <CheckCircle2 size={12} /> Online
            </span>
          ) : status === 'waking' ? (
            <span className="status-pill waking">
              <RefreshCw size={12} className="spinning" /> Waking ({wakeCountdown}s)...
            </span>
          ) : (
            <button
              type="button"
              className="btn-link-action wake-btn"
              onClick={handleWakeUp}
              title="Render free tier puts instances to sleep. Click to wake it up."
            >
              Wake Server
            </button>
          )}

          <button
            type="button"
            className="btn-icon-toggle"
            onClick={() => {
              setShowConfig(!showConfig);
              if (!showConfig) setInputUrl(localStorage.getItem('custom_api_url') || cleanRoot);
            }}
            title="Configure Backend URL"
          >
            <Settings size={14} />
          </button>
        </div>
      </div>

      {statusText && status !== 'online' && (
        <div className={`status-note ${status}`}>
          {status === 'offline' && <AlertCircle size={12} />}
          <span>{statusText}</span>
        </div>
      )}

      {showConfig && (
        <div className="backend-config-drawer">
          <label className="config-label">
            Render Backend Service URL
            <span className="config-hint">(from Render Dashboard: enterprise-ai-backend)</span>
          </label>
          <div className="config-input-group">
            <input
              type="text"
              className="input input-sm config-input"
              placeholder="https://enterprise-ai-backend-xxxx.onrender.com"
              value={inputUrl}
              onChange={(e) => setInputUrl(e.target.value)}
            />
            <button
              type="button"
              className="btn btn-primary btn-sm"
              onClick={handleSaveUrl}
            >
              Save
            </button>
          </div>

          <div className="config-footer-buttons">
            <button
              type="button"
              className="btn btn-secondary btn-xs"
              onClick={() => checkHealth(true)}
            >
              <RefreshCw size={11} /> Test Ping
            </button>
            <button
              type="button"
              className="btn btn-secondary btn-xs"
              onClick={handleSeedDatabase}
              disabled={seeding}
              title="Create tables and default admin/demo users"
            >
              <Database size={11} /> {seeding ? 'Seeding...' : 'Seed DB'}
            </button>
            <button
              type="button"
              className="btn btn-ghost btn-xs text-muted"
              onClick={() => {
                setCustomApiUrl(null);
                setCleanRoot(getCleanBackendRoot());
                setInputUrl('');
                toast.success('Reset to auto-detected URL');
              }}
            >
              Reset
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
