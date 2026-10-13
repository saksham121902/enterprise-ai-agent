import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

const api = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
});

// Attach JWT token to every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle 401 responses (token expired)
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      const refreshToken = localStorage.getItem('refresh_token');
      if (refreshToken) {
        try {
          const { data } = await axios.post(`${API_BASE}/auth/refresh`, {
            refresh_token: refreshToken,
          });
          localStorage.setItem('access_token', data.access_token);
          localStorage.setItem('refresh_token', data.refresh_token);
          error.config.headers.Authorization = `Bearer ${data.access_token}`;
          return api.request(error.config);
        } catch {
          localStorage.removeItem('access_token');
          localStorage.removeItem('refresh_token');
          window.location.href = '/login';
        }
      } else {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

// ── Auth API ──────────────────────────────────────────────────────────

export const authApi = {
  register: (data: { email: string; username: string; password: string; full_name: string }) =>
    api.post('/auth/register', data),
  login: (data: { login: string; password: string }) =>
    api.post('/auth/login', data),
  getMe: () => api.get('/auth/me'),
  changePassword: (data: { current_password: string; new_password: string }) =>
    api.post('/auth/change-password', data),
  logout: () => api.post('/auth/logout'),
};

// ── Chat API ──────────────────────────────────────────────────────────

export const chatApi = {
  sendMessage: (data: { message: string; chat_id?: string }) =>
    api.post('/chat/message', data),
  listChats: () => api.get('/chat/'),
  getChat: (chatId: string) => api.get(`/chat/${chatId}`),
  deleteChat: (chatId: string) => api.delete(`/chat/${chatId}`),
};

// ── Document API ──────────────────────────────────────────────────────

export const documentApi = {
  upload: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post('/documents/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  list: () => api.get('/documents/'),
  get: (docId: string) => api.get(`/documents/${docId}`),
  delete: (docId: string) => api.delete(`/documents/${docId}`),
};

// ── Analytics API ─────────────────────────────────────────────────────

export const analyticsApi = {
  overview: () => api.get('/analytics/overview'),
  costBreakdown: () => api.get('/analytics/cost-breakdown'),
};

// ── Workflow API ──────────────────────────────────────────────────────

export const workflowApi = {
  list: () => api.get('/workflows/'),
  get: (workflowId: string) => api.get(`/workflows/${workflowId}`),
};

// ── Memory API ────────────────────────────────────────────────────

export const memoryApi = {
  list: () => api.get('/memory/'),
  create: (data: { memory_type: string; content: string; importance_score?: number; source?: string }) =>
    api.post('/memory/', data),
  delete: (memoryId: string) => api.delete(`/memory/${memoryId}`),
};

// ── Approval API ──────────────────────────────────────────────────

export const approvalApi = {
  list: (status?: string) =>
    api.get('/approvals/', { params: status ? { status } : {} }),
  approve: (approvalId: string, notes?: string) =>
    api.post(`/approvals/${approvalId}/approve`, notes ? { notes } : {}),
  reject: (approvalId: string, notes?: string) =>
    api.post(`/approvals/${approvalId}/reject`, notes ? { notes } : {}),
};

export default api;

