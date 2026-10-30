'use client';

import React, { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/contexts/AuthContext';
import { 
  LayoutDashboard, 
  FileText, 
  BarChart3, 
  Activity,
  Upload,
  FolderOpen,
  ArrowRight,
  Sparkles
} from 'lucide-react';

export default function HomePage() {
  const { isAuthenticated } = useAuth();
  const router = useRouter();

  // Simple redirect check - no loading screen needed
  useEffect(() => {
    if (!isAuthenticated) {
      router.replace('/login');
    }
  }, [isAuthenticated, router]);

  // Don't show loading screen - just render nothing if not authenticated
  if (!isAuthenticated) {
    return null;
  }

  // Don't render anything if not authenticated (will redirect)
  if (!isAuthenticated) {
    return null;
  }

  const navigationCards = [
    {
      title: 'Dashboard',
      description: 'Rechnungen verwalten und bearbeiten',
      icon: LayoutDashboard,
      href: '/dashboard',
      gradient: 'from-blue-500 to-blue-600',
      bgGradient: 'from-blue-50 to-blue-100'
    },
    {
      title: 'Hochladen',
      description: 'Rechnungen per Drag & Drop hochladen',
      icon: Upload,
      href: '/upload',
      gradient: 'from-emerald-500 to-emerald-600',
      bgGradient: 'from-emerald-50 to-emerald-100'
    },
    {
      title: 'Ordnerüberwachung',
      description: 'Automatische Dateiüberwachung konfigurieren',
      icon: FolderOpen,
      href: '/dashboard/folder-watcher',
      gradient: 'from-orange-500 to-orange-600',
      bgGradient: 'from-orange-50 to-orange-100'
    },
    {
      title: 'Prüfbericht',
      description: 'Skonto-Berichte und Analysen anzeigen',
      icon: BarChart3,
      href: '/prufbericht',
      gradient: 'from-purple-500 to-purple-600',
      bgGradient: 'from-purple-50 to-purple-100'
    },
    {
      title: 'Systemstatus',
      description: 'Systemzustand und Status überwachen',
      icon: Activity,
      href: '/health',
      gradient: 'from-green-500 to-green-600',
      bgGradient: 'from-green-50 to-green-100'
    },
    {
      title: 'Rechnungen',
      description: 'Schnellzugriff auf Rechnungsverwaltung',
      icon: FileText,
      href: '/dashboard',
      gradient: 'from-indigo-500 to-indigo-600',
      bgGradient: 'from-indigo-50 to-indigo-100'
    }
  ];

  return (
    <div className="min-h-screen gradient-bg-light relative overflow-hidden">
      {/* Floating Background Elements */}
      <div className="absolute top-20 left-10 w-32 h-32 bg-purple-300 rounded-full mix-blend-multiply filter blur-xl opacity-70 animate-float"></div>
      <div className="absolute top-40 right-20 w-40 h-40 bg-blue-300 rounded-full mix-blend-multiply filter blur-xl opacity-70 animate-float" style={{ animationDelay: '2s' }}></div>
      <div className="absolute bottom-20 left-1/3 w-36 h-36 bg-pink-300 rounded-full mix-blend-multiply filter blur-xl opacity-70 animate-float" style={{ animationDelay: '4s' }}></div>
      
      <div className="relative z-10 pt-24 pb-12 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto">
          {/* Header Section */}
          <div className="text-center mb-16">
            <div className="glass-card rounded-2xl p-8 mb-8 border-0 shadow-xl animate-fade-in">
              <div className="flex items-center justify-center mb-4">
                <div className="w-16 h-16 bg-gradient-to-r from-purple-600 to-blue-600 rounded-xl flex items-center justify-center shadow-lg animate-glow">
                  <FileText className="h-8 w-8 text-white" />
                </div>
              </div>
              <h1 className="text-4xl font-bold mb-4">
                <span className="bg-gradient-to-r from-purple-600 via-blue-600 to-indigo-600 bg-clip-text text-transparent">
                  Willkommen beim OCR Rechnungsverarbeiter
                </span>
              </h1>
              <p className="text-xl text-gray-600 max-w-3xl mx-auto">
                Optimieren Sie Ihre Rechnungsverarbeitung mit automatisierten Workflows und digitaler Dokumentenverwaltung
              </p>
            </div>
          </div>

          {/* Navigation Cards Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
            {navigationCards.map((card, index) => (
              <Link
                key={card.title}
                href={card.href}
                className="group glass-card rounded-2xl p-6 border-0 shadow-lg hover:shadow-2xl transition-all duration-300 transform hover:scale-105 animate-fade-in"
                style={{ animationDelay: `${index * 0.1}s` }}
              >
                <div className="text-center">
                  <div className={`w-16 h-16 bg-gradient-to-r ${card.gradient} rounded-xl flex items-center justify-center mx-auto mb-4 group-hover:scale-110 transition-transform duration-300 shadow-lg`}>
                    <card.icon className="h-8 w-8 text-white" />
                  </div>
                  <h3 className="text-xl font-semibold gradient-text mb-2 group-hover:scale-105 transition-transform duration-300">
                    {card.title}
                  </h3>
                  <p className="text-gray-600 mb-4 text-sm">
                    {card.description}
                  </p>
                  <div className="flex items-center justify-center text-purple-600 group-hover:text-purple-700 transition-colors">
                    <span className="text-sm font-medium">Los geht’s</span>
                    <ArrowRight className="h-4 w-4 ml-1 group-hover:translate-x-1 transition-transform duration-300" />
                  </div>
                </div>
              </Link>
            ))}
          </div>

          {/* Quick Stats Section */}
          <div className="mt-16">
            <div className="glass-card rounded-2xl p-8 border-0 shadow-xl animate-fade-in">
              <h2 className="text-2xl font-bold gradient-text text-center mb-8">
                Systemübersicht
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className="text-center">
                  <div className="text-3xl font-bold gradient-text mb-2">Digital</div>
                  <div className="text-gray-600">Dokumentenverwaltung</div>
                </div>
                <div className="text-center">
                  <div className="text-3xl font-bold gradient-text mb-2">Automatisiert</div>
                  <div className="text-gray-600">Workflow-Verarbeitung</div>
                </div>
                <div className="text-center">
                  <div className="text-3xl font-bold gradient-text mb-2">Echtzeit</div>
                  <div className="text-gray-600">Status-Verfolgung</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
