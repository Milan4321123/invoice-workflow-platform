'use client'

import React, { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import Dropzone from '@/components/Dropzone'
import toast from 'react-hot-toast'

interface UploadedFile {
  id: string
  url: string
  status: string
  filename: string
  file_size: number
  message: string
}

export default function UploadPage() {
  const [uploadedFile, setUploadedFile] = useState<UploadedFile | null>(null)
  const [isUploading, setIsUploading] = useState(false)
  const router = useRouter()

  const handleUploadStart = () => {
    setIsUploading(true)
    toast.loading('Datei wird hochgeladen...', { id: 'upload' })
  }

  const handleUploadComplete = (data: UploadedFile) => {
    setUploadedFile(data)
    setIsUploading(false)
    toast.success('Datei erfolgreich hochgeladen!', { id: 'upload' })
  }

  const handleUploadError = (error: string) => {
    setIsUploading(false)
    toast.error(error, { id: 'upload' })
  }

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes'
    const k = 1024
    const sizes = ['Bytes', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
  }

  const navigateToDashboard = () => {
    router.push('/dashboard')
  }

  const uploadAnother = () => {
    setUploadedFile(null)
  }

  return (
    <div className="min-h-screen gradient-bg-light pt-20 pb-12"> {/* Added modern background */}
      
      <div className="max-w-2xl mx-auto px-2 sm:px-4">
        <div className="mb-8">
          <Link 
            href="/dashboard" 
            className="text-blue-600 hover:text-purple-600 flex items-center gap-2 mb-4 transition-colors font-medium"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            Zurück zum Dashboard
          </Link>
          
          <div className="glass-card rounded-xl p-6 border-0 shadow-xl animate-fade-in">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-12 h-12 bg-gradient-to-r from-emerald-500 to-emerald-600 rounded-xl flex items-center justify-center shadow-lg">
                <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                </svg>
              </div>
              <div>
                <h1 className="text-3xl font-bold gradient-text">Rechnung hochladen</h1>
                <p className="text-gray-600 mt-1">
                  Laden Sie Ihre PDF-Rechnung für die Speicherung und manuelle Bearbeitung mit durchsuchbaren Dropdown-Menüs hoch.
                </p>
              </div>
            </div>
          </div>
        </div>

        {!uploadedFile ? (
          <div className="space-y-6">
            <Dropzone
              onUploadStart={handleUploadStart}
              onUploadComplete={handleUploadComplete}
              onUploadError={handleUploadError}
            />
            
            <div className="glass-card rounded-xl p-6 border border-amber-200 shadow-lg animate-fade-in">
              <h3 className="font-medium gradient-text mb-3 flex items-center gap-2">
                <svg className="w-5 h-5 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                Dateinamen-Anforderungen:
              </h3>
              <p className="text-sm text-gray-700 mb-3">
                <code className="glass-card px-3 py-1 rounded-lg font-mono text-purple-700 border border-purple-200">
                  YYYYMMDD_IDENTIFIER_VENDOR_TYPE.pdf
                </code>
              </p>
              <ul className="text-sm text-gray-700 space-y-2">
                <li className="flex items-center gap-2">
                  <div className="w-2 h-2 bg-gradient-to-r from-purple-500 to-blue-500 rounded-full"></div>
                  <strong>JJJJMMTT:</strong> Datum im Format (z.B. 20241201)
                </li>
                <li className="flex items-center gap-2">
                  <div className="w-2 h-2 bg-gradient-to-r from-purple-500 to-blue-500 rounded-full"></div>
                  <strong>KENNUNG:</strong> Rechnungs- oder Bestellnummer (z.B. INV001)
                </li>
                <li className="flex items-center gap-2">
                  <div className="w-2 h-2 bg-gradient-to-r from-purple-500 to-blue-500 rounded-full"></div>
                  <strong>LIEFERANT:</strong> Firmenname (z.B. ACME)
                </li>
                <li className="flex items-center gap-2">
                  <div className="w-2 h-2 bg-gradient-to-r from-purple-500 to-blue-500 rounded-full"></div>
                  <strong>TYP:</strong> Dokumenttyp (z.B. SUPPLY, SERVICE)
                </li>
              </ul>
            </div>
          </div>
        ) : (
          <div className="glass-card border border-green-200 rounded-xl p-6 shadow-xl animate-fade-in">
            <div className="flex items-center mb-4">
              <div className="w-12 h-12 bg-gradient-to-r from-green-500 to-green-600 rounded-xl flex items-center justify-center mr-3 shadow-lg">
                <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <h2 className="text-lg font-semibold gradient-text">Upload erfolgreich!</h2>
            </div>
            
            <div className="space-y-3 mb-6 text-gray-700">
              <p className="flex justify-between">
                <strong>Dateiname:</strong> 
                <span className="font-mono text-sm">{uploadedFile.filename}</span>
              </p>
              <p className="flex justify-between">
                <strong>Dateigröße:</strong> 
                <span className="font-mono text-sm">{formatFileSize(uploadedFile.file_size)}</span>
              </p>
              <p className="flex justify-between">
                <strong>Status:</strong> 
                <span className="font-mono text-sm text-green-600">{uploadedFile.status}</span>
              </p>
              <p className="flex justify-between">
                <strong>Datei-ID:</strong> 
                <span className="font-mono text-sm text-purple-600">{uploadedFile.id}</span>
              </p>
            </div>
            
            <div className="flex gap-4">
              <button
                onClick={navigateToDashboard}
                className="bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 text-white px-6 py-2 rounded-xl font-medium transition-all transform hover:scale-105 shadow-lg"
              >
                Dashboard anzeigen
              </button>
              <button
                onClick={uploadAnother}
                className="glass-card hover:bg-white/20 text-gray-800 px-6 py-2 rounded-xl font-medium transition-all transform hover:scale-105 border border-gray-200 shadow-lg"
              >
                Weitere Datei hochladen
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
