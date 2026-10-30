'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import { 
  Home,
  LayoutDashboard, 
  FileText, 
  BarChart3, 
  Activity,
  Upload,
  FolderOpen,
  Menu, 
  X,
  ChevronDown,
  LogOut,
  User,
  Bell,
  Settings,
  ShieldCheck
} from 'lucide-react';

const Navigation = () => {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [isProfileDropdownOpen, setIsProfileDropdownOpen] = useState(false);
  const pathname = usePathname();
  const router = useRouter();
  const { logout, user } = useAuth();

  const handleSignOut = () => {
    console.log('🚪 Sign out button clicked');
    logout();
    setIsProfileDropdownOpen(false);
    router.replace('/login');
  };

  const navItems = [
    { href: '/', label: 'Startseite', icon: Home },
    { href: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { href: '/upload', label: 'Hochladen', icon: Upload },
    { href: '/dashboard/folder-watcher', label: 'Ordnerüberwachung', icon: FolderOpen },
    { href: '/prufbericht', label: 'Prüfbericht', icon: BarChart3 },
    { href: '/health', label: 'Systemstatus', icon: Activity },
    { href: '/datenschutz-anfragen', label: 'Datenschutz', icon: ShieldCheck },
  ];

  const isActiveRoute = (href: string) => {
    return pathname === href || pathname?.startsWith(href + '/');
  };

  return (
    <nav className="fixed top-0 left-0 right-0 z-50 glass-nav">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          {/* Logo and Brand */}
          <div className="flex items-center">
            <Link href="/dashboard" className="flex items-center space-x-3">
              <div className="w-10 h-10 bg-gradient-to-r from-purple-600 to-blue-600 rounded-lg flex items-center justify-center shadow-lg">
                <FileText className="h-6 w-6 text-white" />
              </div>
              <div className="hidden md:block">
                <h1 className="text-xl font-bold bg-gradient-to-r from-purple-600 to-blue-600 bg-clip-text text-transparent">
                  OCR Invoice
                </h1>
                <p className="text-xs text-gray-500">Processor</p>
              </div>
            </Link>
          </div>

          {/* Desktop Navigation */}
          <div className="hidden lg:flex items-center space-x-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = isActiveRoute(item.href);
              
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`
                    relative px-3 py-2 rounded-lg text-sm font-medium transition-all duration-200
                    flex items-center space-x-2 group
                    ${isActive 
                      ? 'bg-gradient-to-r from-purple-600 to-blue-600 text-white shadow-lg' 
                      : 'text-gray-700 hover:bg-white/50 hover:shadow-md'
                    }
                  `}
                >
                  <Icon className={`h-4 w-4 ${isActive ? 'text-white' : 'text-gray-500 group-hover:text-gray-700'}`} />
                  <span className="hidden xl:block">{item.label}</span>
                  {isActive && (
                    <div className="absolute -bottom-1 left-1/2 transform -translate-x-1/2 w-1 h-1 bg-white rounded-full"></div>
                  )}
                </Link>
              );
            })}
          </div>

          {/* User Menu and Mobile Toggle */}
          <div className="flex items-center space-x-2">
            {/* Notifications */}
            <button className="relative p-2 text-gray-600 hover:text-gray-800 hover:bg-white/50 rounded-lg transition-all duration-200">
              <Bell className="h-5 w-5" />
              <span className="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full"></span>
            </button>

            {/* User Profile Dropdown */}
            <div className="relative">
              <button
                onClick={() => setIsProfileDropdownOpen(!isProfileDropdownOpen)}
                className="flex items-center space-x-2 p-2 rounded-lg text-gray-700 hover:bg-white/50 transition-all duration-200"
              >
                <div className="w-8 h-8 bg-gradient-to-r from-purple-600 to-blue-600 rounded-full flex items-center justify-center">
                  <User className="h-4 w-4 text-white" />
                </div>
                <div className="hidden lg:block text-left">
                  <p className="text-sm font-medium">{user?.full_name || user?.username || 'Admin User'}</p>
                  <p className="text-xs text-gray-500">{user?.email || 'user@yourcompany.com'}</p>
                </div>
                <ChevronDown className="h-4 w-4 text-gray-500 hidden lg:block" />
              </button>

              {/* Profile Dropdown */}
              {isProfileDropdownOpen && (
                <div className="absolute right-0 mt-2 w-48 glass-card rounded-lg shadow-xl border-0 py-2">
                  <Link
                    href="/profile"
                    className="flex items-center px-4 py-2 text-sm text-gray-700 hover:bg-white/50 transition-colors"
                  >
                    <User className="h-4 w-4 mr-3" />
                    Profil Einstellungen
                  </Link>
                  <Link
                    href="/settings"
                    className="flex items-center px-4 py-2 text-sm text-gray-700 hover:bg-white/50 transition-colors"
                  >
                    <Settings className="h-4 w-4 mr-3" />
                    System Einstellungen
                  </Link>
                  <hr className="my-2 border-gray-200" />
                  <button 
                    onClick={handleSignOut}
                    className="flex items-center w-full px-4 py-2 text-sm text-red-600 hover:bg-red-50 transition-colors"
                  >
                    <LogOut className="h-4 w-4 mr-3" />
                    Abmelden
                  </button>
                </div>
              )}
            </div>

            {/* Mobile menu button */}
            <button
              onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
              className="lg:hidden p-2 text-gray-600 hover:text-gray-800 hover:bg-white/50 rounded-lg transition-all duration-200"
            >
              {isMobileMenuOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
            </button>
          </div>
        </div>

        {/* Mobile Navigation */}
        {isMobileMenuOpen && (
          <div className="lg:hidden mt-2 pb-4">
            <div className="glass-card rounded-lg p-4 space-y-2">
              {navItems.map((item) => {
                const Icon = item.icon;
                const isActive = isActiveRoute(item.href);
                
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`
                      flex items-center space-x-3 px-4 py-3 rounded-lg text-sm font-medium transition-all duration-200
                      ${isActive 
                        ? 'bg-gradient-to-r from-purple-600 to-blue-600 text-white shadow-lg' 
                        : 'text-gray-700 hover:bg-white/50'
                      }
                    `}
                    onClick={() => setIsMobileMenuOpen(false)}
                  >
                    <Icon className={`h-5 w-5 ${isActive ? 'text-white' : 'text-gray-500'}`} />
                    <span>{item.label}</span>
                  </Link>
                );
              })}
              
              <hr className="my-4 border-gray-200" />
              
              <div className="px-4 py-2">
                <p className="text-sm font-medium text-gray-700">{user?.full_name || user?.username || 'Admin User'}</p>
                <p className="text-xs text-gray-500">{user?.email || 'user@yourcompany.com'}</p>
              </div>
              
              <Link
                href="/profile"
                className="flex items-center space-x-3 px-4 py-2 text-sm text-gray-700 hover:bg-white/50 rounded-lg transition-colors"
                onClick={() => setIsMobileMenuOpen(false)}
              >
                <User className="h-4 w-4" />
                <span>Profil Einstellungen</span>
              </Link>
              
              <Link
                href="/settings"
                className="flex items-center space-x-3 px-4 py-2 text-sm text-gray-700 hover:bg-white/50 rounded-lg transition-colors"
                onClick={() => setIsMobileMenuOpen(false)}
              >
                <Settings className="h-4 w-4" />
                <span>System Einstellungen</span>
              </Link>
              
              <button 
                onClick={handleSignOut}
                className="flex items-center space-x-3 w-full px-4 py-2 text-sm text-red-600 hover:bg-red-50 rounded-lg transition-colors"
              >
                <LogOut className="h-4 w-4" />
                <span>Abmelden</span>
              </button>
            </div>
          </div>
        )}
      </div>
    </nav>
  );
};

export default Navigation;
