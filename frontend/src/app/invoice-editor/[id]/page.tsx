'use client';

import React, { useEffect, useState } from 'react';
import { getApiUrl } from '@/config/api';
import { useParams, useRouter } from 'next/navigation';
import InvoiceEditorDashboard from '@/components/InvoiceEditorDashboard';
import { AlertTriangle, ArrowLeft } from 'lucide-react';
import { authFetch } from '@/lib/authFetch';

export default function InvoiceEditorPage() {
  const params = useParams();
  const router = useRouter();
  const invoiceId = params?.id as string;
  
  const [isValidating, setIsValidating] = useState(true);
  const [isValid, setIsValid] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Validate invoice ID and check if invoice exists
  useEffect(() => {
    const validateInvoice = async () => {
      if (!invoiceId) {
        setError('No invoice ID provided');
        setIsValidating(false);
        return;
      }

      try {
        // Use the existing editor endpoint to validate and fetch invoice data
        const apiUrl = getApiUrl();
        const response = await authFetch(`${apiUrl}/api/invoices/${invoiceId}/editor`);
        
        if (response.ok) {
          setIsValid(true);
        } else if (response.status === 404) {
          setError('Invoice not found');
        } else {
          setError('Failed to validate invoice');
        }
      } catch (err) {
        console.error('Error validating invoice:', err);
        setError('Failed to connect to server');
      } finally {
        setIsValidating(false);
      }
    };

    validateInvoice();
  }, [invoiceId]);

  const handleGoBack = () => {
    router.push('/dashboard');
  };

  // Show loading state while validating
  if (isValidating) {
    return (
      <div className="flex items-center justify-center h-screen gradient-bg-light">
        <div className="text-center glass-card rounded-2xl p-8 animate-fade-in">
          <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-purple-600 mx-auto mb-4"></div>
          <h2 className="text-xl font-semibold gradient-text mb-2">Validating Invoice</h2>
          <p className="text-gray-600">Please wait...</p>
        </div>
      </div>
    );
  }

  // Show error state if validation failed
  if (!isValid || error) {
    return (
      <div className="flex items-center justify-center h-screen gradient-bg-light">
        <div className="text-center max-w-md glass-card rounded-2xl p-8 animate-fade-in">
          <div className="w-16 h-16 bg-gradient-to-r from-red-500 to-red-600 rounded-xl flex items-center justify-center mx-auto mb-4">
            <AlertTriangle className="h-8 w-8 text-white" />
          </div>
          <h2 className="text-xl font-semibold gradient-text mb-2">
            {error || 'Invalid Invoice'}
          </h2>
          <p className="text-gray-600 mb-6">
            {error === 'Invoice not found' 
              ? 'The invoice you\'re looking for doesn\'t exist or has been removed.'
              : 'There was a problem loading this invoice. Please try again or contact support.'
            }
          </p>
          <div className="space-y-3">
            <button
              onClick={handleGoBack}
              className="flex items-center justify-center space-x-2 w-full px-4 py-2 bg-gradient-to-r from-blue-600 to-blue-700 text-white rounded-xl hover:from-blue-700 hover:to-blue-800 transition-all transform hover:scale-105 shadow-lg"
            >
              <ArrowLeft className="h-4 w-4" />
              <span>Back to Dashboard</span>
            </button>
            <button
              onClick={() => window.location.reload()}
              className="w-full px-4 py-2 glass-card text-gray-700 rounded-xl hover:bg-white/20 transition-all transform hover:scale-105 border border-gray-200"
            >
              Try Again
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Render the main invoice editor dashboard
  return (
    <InvoiceEditorDashboard 
      invoiceId={invoiceId}
      // initialData will be loaded by the dashboard component via API
    />
  );
}
