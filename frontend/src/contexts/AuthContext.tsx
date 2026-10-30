"use client";

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { useRouter, usePathname } from 'next/navigation';

const PUBLIC_PATHS = ['/impressum', '/datenschutz'];

interface User {
  id: string;
  username: string;
  email?: string;
  full_name?: string;
  is_active: boolean;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  login: (username: string, password: string) => Promise<{ success: boolean; error?: string }>;
  logout: () => void;
  isLoading: boolean;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

interface AuthProviderProps {
  children: ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false); // Start as false - no loading screen needed
  const router = useRouter();
  const pathname = usePathname();

  const isAuthenticated = !!token && !!user;

  // Load token from localStorage on mount - optimized with better error handling
  useEffect(() => {
    try {
      const savedToken = localStorage.getItem('authToken');
      const savedUser = localStorage.getItem('authUser');
      
      if (savedToken && savedUser) {
        try {
          const parsedUser = JSON.parse(savedUser);
          // Validate that the parsed user has required fields
          if (parsedUser.id && parsedUser.username) {
            setToken(savedToken);
            setUser(parsedUser);
            console.log('✅ Restored auth from localStorage:', parsedUser.username);
          } else {
            console.warn('⚠️ Invalid user data in localStorage, clearing');
            localStorage.removeItem('authToken');
            localStorage.removeItem('authUser');
          }
        } catch (parseError) {
          console.error('❌ Error parsing saved user data:', parseError);
          localStorage.removeItem('authToken');
          localStorage.removeItem('authUser');
        }
      }
    } catch (error) {
      console.error('❌ Error accessing localStorage:', error);
      // localStorage might not be available (SSR, private browsing, etc.)
    }
  }, []);

  // Simplified redirect logic - only redirect if needed
  useEffect(() => {
    const isLoginPage = pathname === '/login';
    // Impressum and privacy notice must be reachable without logging in
    const isPublicPage = isLoginPage || PUBLIC_PATHS.includes(pathname ?? '');
    
    // Add a small delay to prevent race conditions during navigation
    const timer = setTimeout(() => {
      if (!isAuthenticated && !isPublicPage) {
        console.log('🔄 Redirecting to login - not authenticated');
        router.replace('/login');
      } else if (isAuthenticated && isLoginPage) {
        console.log('🔄 Redirecting to dashboard - already authenticated');
        router.replace('/dashboard');
      }
    }, 100); // Small delay to allow authentication state to stabilize
    
    return () => clearTimeout(timer);
  }, [isAuthenticated, pathname, router]);

  const login = async (username: string, password: string): Promise<{ success: boolean; error?: string }> => {
    try {
      setIsLoading(true);
      
      const formData = new FormData();
      formData.append('username', username);
      formData.append('password', password);

      const response = await fetch('/api/auth/login', {
        method: 'POST',
        body: formData,
      });

      const data = await response.json();

      if (data.access_token) {
        // Extract user data from the response
        const userData: User = {
          id: data.id || '1',
          username: data.username,
          email: data.email || '',
          full_name: data.full_name || '',
          is_active: true
        };
        
        setToken(data.access_token);
        setUser(userData);
        
        // Save to localStorage
        localStorage.setItem('authToken', data.access_token);
        localStorage.setItem('authUser', JSON.stringify(userData));
        
        return { success: true };
      } else {
        return { success: false, error: data.detail || 'Login failed' };
      }
    } catch (error) {
      console.error('Login error:', error);
      return { success: false, error: 'Network error' };
    } finally {
      setIsLoading(false);
    }
  };

  const logout = () => {
    console.log('🚪 Logging out user');
    const currentToken = token;
    
    // Immediately clear auth state
    setUser(null);
    setToken(null);
    localStorage.removeItem('authToken');
    localStorage.removeItem('authUser');
    
    // Optional: Call logout endpoint (don't wait for it)
    if (currentToken) {
      fetch('/api/auth/logout', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${currentToken}`,
        },
      }).catch(console.error);
    }
  };

  const value: AuthContextType = {
    user,
    token,
    login,
    logout,
    isLoading,
    isAuthenticated,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};
