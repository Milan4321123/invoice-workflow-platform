import React from 'react'
import './globals.css'
import { Inter } from 'next/font/google'
import ClientWrapper from './ClientWrapper'

const inter = Inter({ subsets: ['latin'] })

export const metadata = {
  title: 'Rechnungsverwaltungssystem',
  description: 'PDF-Rechnungen hochladen und verwalten mit durchsuchbaren Dropdown-Menüs und Workflow-Automatisierung',
  manifest: '/manifest.json',
  appleWebApp: {
    capable: true,
    statusBarStyle: 'default',
    title: 'Invoice Manager',
  },
}

// Users must be able to zoom (WCAG 1.4.4), so no maximum-scale or user-scalable=no
export const viewport = {
  width: 'device-width',
  initialScale: 1,
  themeColor: '#667eea',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="de">
      <body className={inter.className}>
        <ClientWrapper>
          {children}
        </ClientWrapper>
      </body>
    </html>
  )
}
