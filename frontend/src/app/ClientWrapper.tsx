'use client'

import React from 'react'
import { usePathname } from 'next/navigation'
import { AuthProvider, useAuth } from '@/contexts/AuthContext'
import Navigation from '@/components/Navigation'
import LegalFooter from '@/components/LegalFooter'

interface ClientWrapperProps {
  children: React.ReactNode
}

function AppContent({ children }: ClientWrapperProps) {
  const { isAuthenticated } = useAuth(); // Removed isLoading since we don't need it
  const pathname = usePathname()
  
  // Don't show navigation on login page
  const showNavigation = isAuthenticated && pathname !== '/login'

  return (
    <div className="min-h-screen gradient-bg-light relative">
      {/* Optimized background decoration - fewer elements */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -right-40 w-80 h-80 bg-blue-300 rounded-full mix-blend-multiply filter blur-xl opacity-70 animate-float"></div>
        <div className="absolute -bottom-40 -left-40 w-80 h-80 bg-purple-300 rounded-full mix-blend-multiply filter blur-xl opacity-70 animate-float" style={{animationDelay: '2s'}}></div>
      </div>
      
      {showNavigation && <Navigation />}
      <main className={`relative z-10 ${showNavigation ? 'pt-16' : ''}`}>
        {children}
      </main>
      <LegalFooter />
    </div>
  )
}

export default function ClientWrapper({ children }: ClientWrapperProps) {
  return (
    <AuthProvider>
      <AppContent>{children}</AppContent>
    </AuthProvider>
  )
}
