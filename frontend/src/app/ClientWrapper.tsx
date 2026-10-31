'use client'

import React from 'react'
import { usePathname } from 'next/navigation'
import { AuthProvider, useAuth } from '@/contexts/AuthContext'
import Navigation from '@/components/Navigation'
import LegalFooter from '@/components/LegalFooter'
import { DialogProvider } from '@/components/ui/DialogProvider'
import { Toaster } from 'react-hot-toast'
import { toastConfig } from '@/lib/toast-config'
import { LanguageProvider, useT } from '@/i18n/LanguageContext'

interface ClientWrapperProps {
  children: React.ReactNode
}

function AppContent({ children }: ClientWrapperProps) {
  const { isAuthenticated } = useAuth(); // Removed isLoading since we don't need it
  const t = useT()
  const pathname = usePathname()
  
  // Don't show navigation on login page
  const showNavigation = isAuthenticated && pathname !== '/login'

  return (
    <div className="min-h-screen gradient-bg-light relative">
      {/* Optimized background decoration - fewer elements */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div aria-hidden="true" className="absolute -top-40 -right-40 w-80 h-80 bg-blue-300 rounded-full mix-blend-multiply filter blur-xl opacity-70 animate-float"></div>
        <div aria-hidden="true" className="absolute -bottom-40 -left-40 w-80 h-80 bg-purple-300 rounded-full mix-blend-multiply filter blur-xl opacity-70 animate-float" style={{animationDelay: '2s'}}></div>
      </div>
      
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[100] focus:rounded-lg focus:bg-white focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:text-blue-700 focus:shadow-lg"
      >
        {t('app.skipToContent')}
      </a>
      {showNavigation && <Navigation />}
      <main id="main-content" tabIndex={-1} className={`relative z-10 focus:outline-none ${showNavigation ? 'pt-16' : ''}`}>
        {children}
      </main>
      <LegalFooter />
    </div>
  )
}

export default function ClientWrapper({ children }: ClientWrapperProps) {
  return (
    <LanguageProvider>
      <DialogProvider>
        <AuthProvider>
          <AppContent>{children}</AppContent>
        </AuthProvider>
        {/* One place for notifications app-wide, below the fixed navigation */}
        <Toaster {...toastConfig} />
      </DialogProvider>
    </LanguageProvider>
  )
}
