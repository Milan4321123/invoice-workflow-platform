"use client";

import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import toast from "react-hot-toast";
import { buildApiUrl, API_CONFIG } from '@/config/api';
import { api } from '@/services/apiClient';
import { useT } from '@/i18n/LanguageContext';

type UploadStatus = "idle" | "uploading" | "success" | "error";

interface DropzoneProps {
  onUploadComplete?: (data: any) => void;
  onUploadStart?: () => void;
  onUploadError?: (error: string) => void;
}

interface UploadResponse {
  id: string;
  url: string;
  status: string;
  filename: string;
  file_size: number;
  message: string;
  e_invoice_format?: string | null;
}

// Same rule the backend applies after sanitizing (which turns umlauts into "_"):
// EINGANGSDATUM_PROJEKT_GEWERK_LIEFERANT, as PDF or XRechnung XML
const FILENAME_PATTERN = /^\d{8}_[A-Za-z0-9][A-Za-z0-9.-]*_[A-Za-z0-9][A-Za-z0-9.-]*_[A-Za-z0-9][A-Za-z0-9.-]*\.(pdf|xml)$/;
const isXml = (file: File) => file.name.toLowerCase().endsWith('.xml');

export default function Dropzone({ onUploadComplete, onUploadStart, onUploadError }: DropzoneProps) {
  const [status, setStatus] = useState<UploadStatus>("idle");
  const [errorMessage, setErrorMessage] = useState<string>("");
  const [uploadProgress, setUploadProgress] = useState<number>(0);
  const [uploadedFile, setUploadedFile] = useState<UploadResponse | null>(null);
  const t = useT();
  
  const validateFilename = (filename: string): boolean => FILENAME_PATTERN.test(filename);
  
  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };
  
  const onDrop = useCallback(async (files: File[]) => {
    if (files.length === 0) return;
    
    const file = files[0];
    
    // Reset previous state
    setErrorMessage("");
    setUploadedFile(null);
    setUploadProgress(0);
    
    // Validate file type
    if (file.type !== "application/pdf" && !isXml(file)) {
      const errorMsg = t('upload.wrongType');
      setErrorMessage(errorMsg);
      setStatus("error");
      toast.error(errorMsg);
      onUploadError?.(errorMsg);
      return;
    }
    
    // Validate filename format
    if (!validateFilename(file.name)) {
      const errorMsg = t('upload.wrongName');
      setErrorMessage(errorMsg);
      setStatus("error");
      toast.error("Ungültiges Dateinamen-Format");
      onUploadError?.(errorMsg);
      return;
    }
    
    setStatus("uploading");
    onUploadStart?.(); // Call the callback when upload starts
    
    try {
      // Simulate progress for better UX
      const progressInterval = setInterval(() => {
        setUploadProgress((prev) => {
          if (prev >= 90) {
            clearInterval(progressInterval);
            return 90;
          }
          return prev + 10;
        });
      }, 200);
      
      // Use authenticated API client instead of direct fetch
      const data: UploadResponse = await api.uploadFile(file);
      
      clearInterval(progressInterval);
      setUploadProgress(100);
      setStatus("success");
      setUploadedFile(data);
      toast.success(data.e_invoice_format
        ? t('upload.toastEInvoice', { format: data.e_invoice_format })
        : t('upload.toastDone'));
      
      if (onUploadComplete) {
        onUploadComplete(data);
      }
    } catch (error) {
      console.error("Upload error:", error);
      const errorMsg = error instanceof Error ? error.message : "Upload fehlgeschlagen";
      setErrorMessage(errorMsg);
      setStatus("error");
      setUploadProgress(0);
      toast.error(errorMsg);
      onUploadError?.(errorMsg);
    }
  }, [onUploadComplete, onUploadStart, onUploadError, t]);
  
  const { getRootProps, getInputProps, isDragActive } = useDropzone({ 
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'application/xml': ['.xml'],
      'text/xml': ['.xml'],
    },
    maxFiles: 1,
    multiple: false
  });
  
  const resetUpload = () => {
    setStatus("idle");
    setErrorMessage("");
    setUploadedFile(null);
    setUploadProgress(0);
  };
  
  return (
    <div className="w-full">
      <div 
        {...getRootProps()} 
        className={`border-2 border-dashed rounded-2xl p-8 text-center cursor-pointer transition-all duration-300 glass-card shadow-xl
          ${isDragActive ? 'border-blue-400 bg-blue-50/50 scale-[1.02] shadow-2xl' : 'border-purple-300 hover:border-blue-400 hover:shadow-2xl hover:scale-[1.01]'}
          ${status === 'error' ? 'border-red-300 bg-red-50/50' : ''}
          ${status === 'success' ? 'border-green-300 bg-green-50/50' : ''}
          ${status === 'uploading' ? 'border-blue-300 bg-blue-50/50' : ''}`}
      >
        <input {...getInputProps()} />
        
        {status === 'uploading' ? (
          <div className="text-blue-600">
            <div className="w-12 h-12 mx-auto mb-4 bg-gradient-to-r from-blue-500 to-blue-600 rounded-xl flex items-center justify-center animate-pulse">
              <svg className="animate-spin h-6 w-6 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
            </div>
            <p className="text-lg font-medium mb-4 gradient-text">{t('upload.uploading')}</p>
            <div className="w-full glass-card rounded-full h-3 max-w-xs mx-auto border border-blue-200 overflow-hidden">
              <div 
                className="bg-gradient-to-r from-blue-500 to-blue-600 h-full rounded-full transition-all duration-300 animate-pulse" 
                style={{ width: `${uploadProgress}%` }}
              ></div>
            </div>
            <p className="text-sm mt-3 font-medium text-blue-700">{uploadProgress}%</p>
          </div>
        ) : status === 'success' ? (
          <div className="text-green-600">
            <div className="w-12 h-12 mx-auto mb-4 bg-gradient-to-r from-green-500 to-green-600 rounded-xl flex items-center justify-center shadow-lg">
              <svg className="h-6 w-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <p className="text-lg font-medium mb-4 gradient-text">{t('upload.success')}</p>
            {uploadedFile && (
              <div className="text-sm text-gray-700 mt-4 glass-card rounded-xl p-4 border border-green-200">
                <p className="flex justify-between"><strong>{t('upload.file')}</strong> <span className="font-mono">{uploadedFile.filename}</span></p>
                <p className="flex justify-between"><strong>{t('upload.size')}</strong> <span className="font-mono">{formatFileSize(uploadedFile.file_size)}</span></p>
                <p className="flex justify-between"><strong>{t('upload.status')}</strong> <span className="font-mono text-green-600">{uploadedFile.status}</span></p>
                {uploadedFile.e_invoice_format && (
                  <p className="flex justify-between"><strong>{t('upload.eInvoice')}</strong> <span className="font-mono text-green-600">{uploadedFile.e_invoice_format}</span></p>
                )}
              </div>
            )}
            <button 
              onClick={(e) => {
                e.stopPropagation();
                resetUpload();
              }}
              className="mt-4 px-6 py-2 bg-gradient-to-r from-blue-600 to-blue-700 text-white rounded-xl hover:from-blue-700 hover:to-blue-800 transition-all transform hover:scale-105 shadow-lg"
            >
              {t('upload.another')}
            </button>
          </div>
        ) : status === 'error' ? (
          <div className="text-red-600">
            <div className="w-12 h-12 mx-auto mb-4 bg-gradient-to-r from-red-500 to-red-600 rounded-xl flex items-center justify-center shadow-lg">
              <svg className="h-6 w-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z" />
              </svg>
            </div>
            <p className="text-lg font-medium mb-2 gradient-text">{t('upload.failed')}</p>
            <p className="text-sm text-gray-700 glass-card rounded-xl p-3 border border-red-200 mb-4">{errorMessage}</p>
            <button 
              onClick={(e) => {
                e.stopPropagation();
                resetUpload();
              }}
              className="mt-2 px-6 py-2 bg-gradient-to-r from-red-600 to-red-700 text-white rounded-xl hover:from-red-700 hover:to-red-800 transition-all transform hover:scale-105 shadow-lg"
            >
              {t('upload.retry')}
            </button>
          </div>
        ) : (
          <div className="text-gray-600">
            <div className="w-16 h-16 mx-auto mb-4 bg-gradient-to-r from-purple-500 to-blue-500 rounded-xl flex items-center justify-center shadow-lg animate-float">
              <svg className="h-8 w-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
              </svg>
            </div>
            <p className="text-xl font-medium mb-2 gradient-text">
              {isDragActive ? t('upload.dropActive') : t('upload.dropIdle')}
            </p>
            <p className="text-sm text-gray-500 mb-6">{t('upload.orClick')}</p>
            <div className="text-sm text-gray-700 glass-card rounded-xl p-4 max-w-md mx-auto border border-purple-200 shadow-lg">
              <p className="font-medium mb-2 gradient-text">📋 {t('upload.nameRules')}</p>
              <p className="font-mono text-purple-700 mb-1">JJJJMMTT_PROJEKT_GEWERK_LIEFERANT.pdf</p>
              <p className="text-xs text-gray-600 mt-2">
                <span className="font-medium">{t('upload.example')}</span> 20250704_OMEGA_ELEKTRO_Mueller.pdf
              </p>
              <p className="text-xs text-gray-600 mt-2">
                {t('upload.eInvoiceHint')}
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
