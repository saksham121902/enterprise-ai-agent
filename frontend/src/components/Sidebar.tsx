import { NavLink, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  MessageSquare,
  FileText,
  BarChart3,
  GitBranch,
  Settings,
  LogOut,
  ChevronLeft,
  ChevronRight,
  Bot,
  LayoutDashboard,
  Brain,
  ShieldCheck,
} from 'lucide-react';
import { useAuthStore, useUIStore } from '../stores';
import './Sidebar.css';

const navItems = [
  { path: '/', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/chat', label: 'Chat', icon: MessageSquare },
  { path: '/documents', label: 'Documents', icon: FileText },
  { path: '/workflows', label: 'Workflows', icon: GitBranch },
  { path: '/memory', label: 'Memory', icon: Brain },
  { path: '/approvals', label: 'Approvals', icon: ShieldCheck },
  { path: '/analytics', label: 'Analytics', icon: BarChart3 },
  { path: '/settings', label: 'Settings', icon: Settings },
];

export function Sidebar() {
  const { sidebarCollapsed, toggleSidebar } = useUIStore();
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <motion.aside
      className={`sidebar ${sidebarCollapsed ? 'collapsed' : ''}`}
      initial={false}
      animate={{ width: sidebarCollapsed ? 72 : 280 }}
      transition={{ duration: 0.25, ease: 'easeInOut' }}
    >
      {/* Logo */}
      <div className="sidebar-header">
        <div className="sidebar-logo">
          <div className="logo-icon">
            <Bot size={24} />
          </div>
          {!sidebarCollapsed && (
            <motion.span
              className="logo-text"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            >
              AI Agent
            </motion.span>
          )}
        </div>
        <button className="btn-icon btn-ghost collapse-btn" onClick={toggleSidebar}>
          {sidebarCollapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
        </button>
      </div>

      {/* Navigation */}
      <nav className="sidebar-nav">
        {navItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) =>
              `sidebar-link ${isActive ? 'active' : ''}`
            }
            title={sidebarCollapsed ? item.label : undefined}
          >
            <item.icon size={20} />
            {!sidebarCollapsed && <span>{item.label}</span>}
          </NavLink>
        ))}
      </nav>

      {/* User section */}
      <div className="sidebar-footer">
        {!sidebarCollapsed && user && (
          <div className="sidebar-user">
            <div className="user-avatar">
              {user.full_name.charAt(0).toUpperCase()}
            </div>
            <div className="user-info">
              <span className="user-name">{user.full_name}</span>
              <span className="user-role">{user.role_name || 'User'}</span>
            </div>
          </div>
        )}
        <button
          className="sidebar-link logout-btn"
          onClick={handleLogout}
          title="Log out"
        >
          <LogOut size={20} />
          {!sidebarCollapsed && <span>Log out</span>}
        </button>
      </div>
    </motion.aside>
  );
}
