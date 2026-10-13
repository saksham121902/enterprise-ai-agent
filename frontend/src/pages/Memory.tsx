import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Brain,
  Plus,
  Trash2,
  Star,
  Clock,
  Tag,
  Loader2,
  X,
  Sparkles,
} from 'lucide-react';
import { memoryApi } from '../lib/api';
import toast from 'react-hot-toast';
import './Memory.css';

interface MemoryEntry {
  id: string;
  memory_type: string;
  content: string;
  importance_score: number | null;
  source: string | null;
  created_at: string;
}

export function MemoryPage() {
  const [memories, setMemories] = useState<MemoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState({
    memory_type: 'fact',
    content: '',
    importance_score: 5,
    source: '',
  });
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    loadMemories();
  }, []);

  const loadMemories = async () => {
    try {
      const { data } = await memoryApi.list();
      setMemories(data);
    } catch {
      setMemories([]);
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.content.trim()) return;

    setSubmitting(true);
    try {
      await memoryApi.create({
        memory_type: formData.memory_type,
        content: formData.content,
        importance_score: formData.importance_score,
        source: formData.source || undefined,
      });
      toast.success('Memory created');
      setShowForm(false);
      setFormData({ memory_type: 'fact', content: '', importance_score: 5, source: '' });
      loadMemories();
    } catch (err: any) {
      toast.error(err.response?.data?.error?.message || 'Failed to create memory');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (memoryId: string) => {
    if (!confirm('Delete this memory entry?')) return;
    try {
      await memoryApi.delete(memoryId);
      toast.success('Memory deleted');
      loadMemories();
    } catch {
      toast.error('Failed to delete memory');
    }
  };

  const typeColor = (type: string) => {
    switch (type) {
      case 'preference': return '#a855f7';
      case 'fact': return '#3b82f6';
      case 'summary': return '#10b981';
      default: return '#f59e0b';
    }
  };

  const importanceStars = (score: number | null) => {
    if (score === null) return null;
    const filled = Math.round(score / 2);
    return (
      <div className="importance-stars">
        {[1, 2, 3, 4, 5].map((i) => (
          <Star key={i} size={12} className={i <= filled ? 'star-filled' : 'star-empty'} />
        ))}
      </div>
    );
  };

  return (
    <div className="page-content">
      <div className="dashboard-header">
        <div>
          <h1>Memory</h1>
          <p className="text-secondary">Long-term memory entries for AI contextual awareness</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowForm(true)}>
          <Plus size={16} /> New Memory
        </button>
      </div>

      {/* Create form modal */}
      <AnimatePresence>
        {showForm && (
          <motion.div
            className="memory-form-overlay"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setShowForm(false)}
          >
            <motion.div
              className="memory-form-modal glass-card"
              initial={{ opacity: 0, y: 20, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 20, scale: 0.95 }}
              onClick={(e) => e.stopPropagation()}
            >
              <div className="modal-header">
                <h3><Sparkles size={20} /> Create Memory</h3>
                <button className="btn btn-ghost btn-icon" onClick={() => setShowForm(false)}>
                  <X size={18} />
                </button>
              </div>

              <form onSubmit={handleCreate} className="memory-form">
                <div className="form-group">
                  <label>Memory Type</label>
                  <select
                    className="input"
                    value={formData.memory_type}
                    onChange={(e) => setFormData({ ...formData, memory_type: e.target.value })}
                  >
                    <option value="fact">Fact</option>
                    <option value="preference">Preference</option>
                    <option value="summary">Summary</option>
                    <option value="instruction">Instruction</option>
                  </select>
                </div>

                <div className="form-group">
                  <label>Content</label>
                  <textarea
                    className="input memory-textarea"
                    placeholder="What should the AI remember?"
                    value={formData.content}
                    onChange={(e) => setFormData({ ...formData, content: e.target.value })}
                    required
                    rows={4}
                  />
                </div>

                <div className="form-row">
                  <div className="form-group">
                    <label>Importance (1-10)</label>
                    <input
                      type="range"
                      min="1"
                      max="10"
                      value={formData.importance_score}
                      onChange={(e) =>
                        setFormData({ ...formData, importance_score: Number(e.target.value) })
                      }
                      className="range-input"
                    />
                    <span className="range-value">{formData.importance_score}/10</span>
                  </div>

                  <div className="form-group">
                    <label>Source (optional)</label>
                    <input
                      className="input"
                      placeholder="e.g., user, chat, system"
                      value={formData.source}
                      onChange={(e) => setFormData({ ...formData, source: e.target.value })}
                    />
                  </div>
                </div>

                <div className="form-actions">
                  <button type="button" className="btn btn-ghost" onClick={() => setShowForm(false)}>
                    Cancel
                  </button>
                  <button type="submit" className="btn btn-primary" disabled={submitting}>
                    {submitting ? <Loader2 size={16} className="spinning" /> : <Plus size={16} />}
                    Create Memory
                  </button>
                </div>
              </form>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Memory list */}
      <div className="memory-list">
        <AnimatePresence>
          {memories.map((mem, i) => (
            <motion.div
              key={mem.id}
              className="memory-card glass-card"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, x: -20 }}
              transition={{ delay: i * 0.05 }}
            >
              <div className="memory-type-indicator" style={{ background: typeColor(mem.memory_type) }} />
              <div className="memory-body">
                <div className="memory-header">
                  <span
                    className="badge"
                    style={{
                      background: typeColor(mem.memory_type) + '15',
                      color: typeColor(mem.memory_type),
                      border: `1px solid ${typeColor(mem.memory_type)}30`,
                    }}
                  >
                    <Tag size={10} />
                    {mem.memory_type}
                  </span>
                  {importanceStars(mem.importance_score)}
                  <span className="text-xs text-tertiary">
                    <Clock size={10} /> {new Date(mem.created_at).toLocaleDateString()}
                  </span>
                </div>
                <p className="memory-content">{mem.content}</p>
                {mem.source && (
                  <span className="memory-source text-xs text-tertiary">
                    Source: {mem.source}
                  </span>
                )}
              </div>
              <button
                className="btn btn-ghost btn-icon memory-delete"
                onClick={() => handleDelete(mem.id)}
                title="Delete memory"
              >
                <Trash2 size={16} />
              </button>
            </motion.div>
          ))}
        </AnimatePresence>

        {!loading && memories.length === 0 && (
          <div className="empty-state">
            <Brain size={48} strokeWidth={1} />
            <h3>No memories yet</h3>
            <p className="text-secondary">
              Create memory entries to help the AI agent remember important facts,
              preferences, and context across sessions.
            </p>
            <button className="btn btn-primary" onClick={() => setShowForm(true)}>
              <Plus size={16} /> Create First Memory
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
