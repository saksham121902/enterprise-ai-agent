import { useEffect, useState, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Upload,
  FileText,
  Trash2,
  Clock,
  CheckCircle2,
  AlertCircle,
  Loader2,
  File,
  HardDrive,
} from 'lucide-react';
import { documentApi } from '../lib/api';
import toast from 'react-hot-toast';
import './Documents.css';

interface Document {
  id: string;
  original_filename: string;
  file_type: string;
  file_size_bytes: number;
  status: string;
  chunk_count: number;
  created_at: string;
}

export function DocumentsPage() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [uploading, setUploading] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    loadDocuments();
  }, []);

  const loadDocuments = async () => {
    try {
      const { data } = await documentApi.list();
      setDocuments(data);
    } catch {}
  };

  const handleUpload = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setUploading(true);

    for (const file of Array.from(files)) {
      try {
        await documentApi.upload(file);
        toast.success(`${file.name} uploaded`);
      } catch (err: any) {
        toast.error(err.response?.data?.error?.message || `Failed to upload ${file.name}`);
      }
    }

    setUploading(false);
    loadDocuments();
  };

  const handleDelete = async (docId: string) => {
    if (!confirm('Delete this document?')) return;
    try {
      await documentApi.delete(docId);
      toast.success('Document deleted');
      loadDocuments();
    } catch {
      toast.error('Failed to delete');
    }
  };

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  };

  const statusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle2 size={16} className="status-completed" />;
      case 'processing':
        return <Loader2 size={16} className="spinning status-processing" />;
      case 'failed':
        return <AlertCircle size={16} className="status-failed" />;
      default:
        return <Clock size={16} className="status-pending" />;
    }
  };

  return (
    <div className="page-content">
      <div className="dashboard-header">
        <div>
          <h1>Documents</h1>
          <p className="text-secondary">Upload and manage documents for RAG-powered Q&A</p>
        </div>
      </div>

      {/* Upload zone */}
      <motion.div
        className={`upload-zone glass-card ${dragActive ? 'drag-active' : ''}`}
        onDragOver={(e) => { e.preventDefault(); setDragActive(true); }}
        onDragLeave={() => setDragActive(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragActive(false);
          handleUpload(e.dataTransfer.files);
        }}
        onClick={() => fileInputRef.current?.click()}
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept=".pdf,.docx,.txt,.xlsx,.csv"
          onChange={(e) => handleUpload(e.target.files)}
          hidden
        />
        <div className="upload-icon">
          {uploading ? <Loader2 size={32} className="spinning" /> : <Upload size={32} />}
        </div>
        <h3>{uploading ? 'Uploading...' : 'Drop files here or click to upload'}</h3>
        <p className="text-secondary text-sm">PDF, DOCX, TXT, XLSX, CSV — Max 50MB per file</p>
      </motion.div>

      {/* Document list */}
      <div className="doc-list">
        <AnimatePresence>
          {documents.map((doc, i) => (
            <motion.div
              key={doc.id}
              className="doc-item glass-card"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, x: -20 }}
              transition={{ delay: i * 0.05 }}
            >
              <div className="doc-icon">
                <FileText size={24} />
              </div>
              <div className="doc-info">
                <h4 className="doc-name">{doc.original_filename}</h4>
                <div className="doc-meta">
                  <span><File size={12} /> {doc.file_type.toUpperCase()}</span>
                  <span><HardDrive size={12} /> {formatSize(doc.file_size_bytes)}</span>
                  {doc.chunk_count > 0 && <span>{doc.chunk_count} chunks</span>}
                  <span><Clock size={12} /> {new Date(doc.created_at).toLocaleDateString()}</span>
                </div>
              </div>
              <div className="doc-status">
                {statusIcon(doc.status)}
                <span className={`badge badge-${doc.status === 'completed' ? 'success' : doc.status === 'failed' ? 'error' : 'info'}`}>
                  {doc.status}
                </span>
              </div>
              <button
                className="btn btn-ghost btn-icon"
                onClick={(e) => { e.stopPropagation(); handleDelete(doc.id); }}
                title="Delete document"
              >
                <Trash2 size={16} />
              </button>
            </motion.div>
          ))}
        </AnimatePresence>

        {documents.length === 0 && !uploading && (
          <div className="empty-state">
            <FileText size={48} strokeWidth={1} />
            <h3>No documents yet</h3>
            <p className="text-secondary">Upload your first document to get started with AI-powered Q&A</p>
          </div>
        )}
      </div>
    </div>
  );
}
