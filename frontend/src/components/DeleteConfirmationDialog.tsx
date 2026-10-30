'use client'

import React, { useState } from 'react'
import { AlertTriangle, X } from 'lucide-react'

interface DeleteConfirmationDialogProps {
  isOpen: boolean
  fileName: string
  onConfirm: (alsoDeleteFromFolder?: boolean) => void
  onCancel: () => void
  uploadSource?: 'drag-drop' | 'folder-watcher' | 'manual' | 'unknown'
}

export default function DeleteConfirmationDialog({
  isOpen,
  fileName,
  onConfirm,
  onCancel,
  uploadSource = 'unknown'
}: DeleteConfirmationDialogProps) {
  const [confirmText, setConfirmText] = useState('')
  const [isSecondStep, setIsSecondStep] = useState(false)
  const [alsoDeleteFromFolder, setAlsoDeleteFromFolder] = useState(false)

  if (!isOpen) return null

  const getUploadSourceText = () => {
    switch (uploadSource) {
      case 'folder-watcher':
        return 'Diese Rechnung wurde automatisch über den Ordner-Watcher hochgeladen.'
      case 'drag-drop':
        return 'Diese Rechnung wurde per Drag & Drop hochgeladen.'
      case 'manual':
        return 'Diese Rechnung wurde manuell hochgeladen.'
      default:
        return 'Diese Rechnung wurde hochgeladen.'
    }
  }

  const getWarningText = () => {
    if (uploadSource === 'folder-watcher') {
      return 'Achtung: Wenn Sie diese Datei löschen, wird sie nicht automatisch erneut hochgeladen, auch wenn sie noch im überwachten Ordner vorhanden ist.'
    }
    return 'Diese Aktion kann nicht rückgängig gemacht werden.'
  }

  const handleFirstConfirm = () => {
    setIsSecondStep(true)
  }

  const handleFinalConfirm = () => {
    if (confirmText.toLowerCase() === 'löschen') {
      onConfirm()
      // Reset state
      setIsSecondStep(false)
      setConfirmText('')
    }
  }

  const handleCancel = () => {
    onCancel()
    // Reset state
    setIsSecondStep(false)
    setConfirmText('')
  }

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 animate-fade-in">
      <div className="glass-card rounded-xl p-6 max-w-md w-full mx-4 shadow-2xl border-0 animate-fade-in">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center space-x-2">
            <div className="w-8 h-8 bg-gradient-to-r from-red-500 to-red-600 rounded-lg flex items-center justify-center">
              <AlertTriangle className="h-5 w-5 text-white" />
            </div>
            <h3 className="text-lg font-semibold gradient-text">
              Rechnung löschen
            </h3>
          </div>
          <button
            onClick={handleCancel}
            className="text-gray-500 hover:text-gray-700 glass-card p-1 rounded-lg transition-all hover:scale-110"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {!isSecondStep ? (
          <>
            <div className="mb-4">
              <p className="text-gray-700 mb-2">
                Möchten Sie die folgende Rechnung wirklich löschen?
              </p>
              <div className="glass-card p-3 rounded-xl mb-3 border border-white/20">
                <p className="font-medium gradient-text">{fileName}</p>
                <p className="text-sm text-gray-600 mt-1">{getUploadSourceText()}</p>
              </div>
              <div className="glass-card border border-yellow-200 rounded-xl p-3">
                <p className="text-sm text-yellow-800">{getWarningText()}</p>
              </div>
            </div>

            <div className="flex space-x-3">
              <button
                onClick={handleCancel}
                className="flex-1 px-4 py-2 glass-card text-gray-700 rounded-xl hover:bg-white/20 transition-all transform hover:scale-105 border border-gray-200"
              >
                Abbrechen
              </button>
              <button
                onClick={handleFirstConfirm}
                className="flex-1 px-4 py-2 bg-gradient-to-r from-red-600 to-red-700 text-white rounded-xl hover:from-red-700 hover:to-red-800 transition-all transform hover:scale-105 shadow-lg"
              >
                Ja, löschen
              </button>
            </div>
          </>
        ) : (
          <>
            <div className="mb-4">
              <p className="text-gray-700 mb-3">
                Sind Sie sich absolut sicher? Diese Aktion kann nicht rückgängig gemacht werden.
              </p>
              <div className="glass-card border border-red-200 rounded-xl p-3 mb-4">
                <p className="text-sm text-red-800 font-medium mb-2">
                  Geben Sie „LÖSCHEN“ ein, um zu bestätigen:
                </p>
                <input
                  type="text"
                  value={confirmText}
                  onChange={(e) => setConfirmText(e.target.value)}
                  placeholder="Geben Sie LÖSCHEN ein..."
                  className="w-full px-3 py-2 glass-card border border-red-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-red-500 focus:border-transparent transition-all"
                  autoFocus
                />
              </div>
            </div>

            <div className="flex space-x-3">
              <button
                onClick={handleCancel}
                className="flex-1 px-4 py-2 glass-card text-gray-700 rounded-xl hover:bg-white/20 transition-all transform hover:scale-105 border border-gray-200"
              >
                Abbrechen
              </button>
              <button
                onClick={handleFinalConfirm}
                disabled={confirmText.toLowerCase() !== 'löschen'}
                className={`flex-1 px-4 py-2 rounded-xl transition-all transform hover:scale-105 ${
                  confirmText.toLowerCase() === 'löschen'
                    ? 'bg-gradient-to-r from-red-600 to-red-700 text-white hover:from-red-700 hover:to-red-800 shadow-lg'
                    : 'glass-card text-gray-500 cursor-not-allowed border border-gray-200'
                }`}
              >
                Endgültig löschen
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
