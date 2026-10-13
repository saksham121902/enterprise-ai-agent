import { create } from 'zustand';

interface User {
  id: string;
  email: string;
  username: string;
  full_name: string;
  is_active: boolean;
  is_verified: boolean;
  role_name: string | null;
  tenant_id: string;
}

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (user: User, accessToken: string, refreshToken: string) => void;
  logout: () => void;
  setUser: (user: User) => void;
  setLoading: (loading: boolean) => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isAuthenticated: !!localStorage.getItem('access_token'),
  isLoading: true,

  login: (user, accessToken, refreshToken) => {
    localStorage.setItem('access_token', accessToken);
    localStorage.setItem('refresh_token', refreshToken);
    set({ user, isAuthenticated: true, isLoading: false });
  },

  logout: () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    set({ user: null, isAuthenticated: false, isLoading: false });
  },

  setUser: (user) => set({ user, isAuthenticated: true, isLoading: false }),
  setLoading: (isLoading) => set({ isLoading }),
}));

// ── Chat Store ────────────────────────────────────────────────────────

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  model?: string;
  reasoning_steps?: ReasoningStep[];
  processing_time_ms?: number;
  cost_usd?: number;
  created_at: string;
}

interface ReasoningStep {
  agent: string;
  action: string;
  reasoning?: string;
  duration_ms: number;
  model?: string;
  tokens: number;
}

interface ChatSession {
  id: string;
  title: string;
  total_messages: number;
  created_at: string;
  updated_at: string;
}

interface ChatState {
  sessions: ChatSession[];
  currentChatId: string | null;
  messages: ChatMessage[];
  isProcessing: boolean;
  setSessions: (sessions: ChatSession[]) => void;
  setCurrentChat: (chatId: string | null) => void;
  setMessages: (messages: ChatMessage[]) => void;
  addMessage: (message: ChatMessage) => void;
  setProcessing: (processing: boolean) => void;
}

export const useChatStore = create<ChatState>((set) => ({
  sessions: [],
  currentChatId: null,
  messages: [],
  isProcessing: false,

  setSessions: (sessions) => set({ sessions }),
  setCurrentChat: (currentChatId) => set({ currentChatId }),
  setMessages: (messages) => set({ messages }),
  addMessage: (message) =>
    set((state) => ({ messages: [...state.messages, message] })),
  setProcessing: (isProcessing) => set({ isProcessing }),
}));

// ── UI Store ──────────────────────────────────────────────────────────

interface UIState {
  sidebarCollapsed: boolean;
  sidebarMobileOpen: boolean;
  toggleSidebar: () => void;
  setSidebarMobile: (open: boolean) => void;
}

export const useUIStore = create<UIState>((set) => ({
  sidebarCollapsed: false,
  sidebarMobileOpen: false,

  toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
  setSidebarMobile: (sidebarMobileOpen) => set({ sidebarMobileOpen }),
}));
