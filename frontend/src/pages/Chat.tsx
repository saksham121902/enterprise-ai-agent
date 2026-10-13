import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Send,
  Plus,
  Bot,
  User,
  Clock,
  Coins,
  Zap,
  ChevronDown,
  ChevronUp,
  Loader2,
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { chatApi } from '../lib/api';
import { useChatStore } from '../stores';
import toast from 'react-hot-toast';
import './Chat.css';

export function ChatPage() {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const {
    messages,
    currentChatId,
    sessions,
    isProcessing,
    addMessage,
    setCurrentChat,
    setMessages,
    setSessions,
    setProcessing,
  } = useChatStore();

  useEffect(() => {
    loadSessions();
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const loadSessions = async () => {
    try {
      const { data } = await chatApi.listChats();
      setSessions(data);
    } catch {}
  };

  const loadChat = async (chatId: string) => {
    try {
      const { data } = await chatApi.getChat(chatId);
      setCurrentChat(chatId);
      setMessages(data.messages || []);
    } catch {
      toast.error('Failed to load chat');
    }
  };

  const handleNewChat = () => {
    setCurrentChat(null);
    setMessages([]);
  };

  const handleSend = async () => {
    if (!input.trim() || isProcessing) return;

    const userMessage = input.trim();
    setInput('');
    setProcessing(true);

    // Add user message to UI immediately
    addMessage({
      id: crypto.randomUUID(),
      role: 'user',
      content: userMessage,
      created_at: new Date().toISOString(),
    });

    try {
      const { data } = await chatApi.sendMessage({
        message: userMessage,
        chat_id: currentChatId || undefined,
      });

      // Set current chat if this was a new chat
      if (!currentChatId) {
        setCurrentChat(data.chat_id);
      }

      // Add AI response
      addMessage({
        id: data.message_id,
        role: 'assistant',
        content: data.content,
        model: data.model,
        reasoning_steps: data.reasoning_steps,
        processing_time_ms: data.processing_time_ms,
        cost_usd: data.cost_usd,
        created_at: new Date().toISOString(),
      });

      loadSessions(); // Refresh session list
    } catch (err: any) {
      toast.error(err.response?.data?.error?.message || 'Failed to send message');
      addMessage({
        id: crypto.randomUUID(),
        role: 'assistant',
        content: 'Sorry, I encountered an error processing your request.',
        created_at: new Date().toISOString(),
      });
    } finally {
      setProcessing(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="chat-page">
      {/* Chat sessions sidebar */}
      <div className="chat-sessions">
        <button className="btn btn-primary w-full" onClick={handleNewChat}>
          <Plus size={16} /> New Chat
        </button>
        <div className="sessions-list">
          {sessions.map((session) => (
            <button
              key={session.id}
              className={`session-item ${currentChatId === session.id ? 'active' : ''}`}
              onClick={() => loadChat(session.id)}
            >
              <span className="session-title">{session.title}</span>
              <span className="session-meta">{session.total_messages} msgs</span>
            </button>
          ))}
        </div>
      </div>

      {/* Chat area */}
      <div className="chat-main">
        <div className="chat-messages">
          {messages.length === 0 && (
            <div className="chat-empty">
              <motion.div
                className="chat-empty-content"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
              >
                <div className="chat-empty-icon">
                  <Bot size={48} />
                </div>
                <h2>Enterprise AI Agent</h2>
                <p className="text-secondary">
                  Ask questions about your documents, query databases, execute workflows,
                  or get insights from your enterprise data.
                </p>
                <div className="chat-suggestions">
                  {[
                    'Summarize the latest quarterly report',
                    'How many active users do we have?',
                    'What are our top-selling products?',
                    'Create a revenue breakdown by region',
                  ].map((suggestion) => (
                    <button
                      key={suggestion}
                      className="suggestion-chip"
                      onClick={() => setInput(suggestion)}
                    >
                      {suggestion}
                    </button>
                  ))}
                </div>
              </motion.div>
            </div>
          )}

          <AnimatePresence>
            {messages.map((msg, i) => (
              <motion.div
                key={msg.id || i}
                className={`message ${msg.role}`}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3 }}
              >
                <div className="message-avatar">
                  {msg.role === 'user' ? <User size={18} /> : <Bot size={18} />}
                </div>
                <div className="message-content">
                  <ReactMarkdown>{msg.content}</ReactMarkdown>

                  {/* Reasoning steps (for AI messages) */}
                  {msg.reasoning_steps && msg.reasoning_steps.length > 0 && (
                    <ReasoningChain steps={msg.reasoning_steps} />
                  )}

                  {/* Metadata */}
                  {msg.role === 'assistant' && msg.processing_time_ms && (
                    <div className="message-meta">
                      <span><Clock size={12} /> {msg.processing_time_ms}ms</span>
                      {msg.model && <span><Zap size={12} /> {msg.model}</span>}
                      {msg.cost_usd !== undefined && msg.cost_usd > 0 && (
                        <span><Coins size={12} /> ${msg.cost_usd.toFixed(4)}</span>
                      )}
                    </div>
                  )}
                </div>
              </motion.div>
            ))}
          </AnimatePresence>

          {isProcessing && (
            <motion.div
              className="message assistant"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
            >
              <div className="message-avatar">
                <Bot size={18} />
              </div>
              <div className="message-content thinking">
                <Loader2 size={16} className="spinning" />
                <span>Thinking...</span>
              </div>
            </motion.div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input area */}
        <div className="chat-input-area">
          <div className="chat-input-container glass-card">
            <textarea
              ref={inputRef}
              className="chat-textarea"
              placeholder="Ask your AI agent anything..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              rows={1}
              disabled={isProcessing}
            />
            <button
              className="btn btn-primary btn-icon send-btn"
              onClick={handleSend}
              disabled={!input.trim() || isProcessing}
            >
              <Send size={18} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function ReasoningChain({ steps }: { steps: any[] }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="reasoning-chain">
      <button className="reasoning-toggle" onClick={() => setExpanded(!expanded)}>
        <Zap size={14} />
        <span>{steps.length} reasoning step{steps.length !== 1 ? 's' : ''}</span>
        {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
      </button>

      <AnimatePresence>
        {expanded && (
          <motion.div
            className="reasoning-steps"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
          >
            {steps.map((step, i) => (
              <div key={i} className="reasoning-step">
                <div className="step-header">
                  <span className="step-agent badge badge-info">{step.agent}</span>
                  <span className="step-action">{step.action}</span>
                  {step.duration_ms > 0 && (
                    <span className="step-duration">{step.duration_ms}ms</span>
                  )}
                </div>
                {step.reasoning && (
                  <p className="step-reasoning">{step.reasoning}</p>
                )}
              </div>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
