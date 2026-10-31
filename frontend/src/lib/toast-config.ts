// Centralized toast configuration for consistent styling across the application
export const toastConfig = {
  position: "top-right" as const,
  containerStyle: { top: 80 },
  toastOptions: {
    duration: 4000,
    style: {
      background: '#ffffff',
      color: '#374151',
      border: '1px solid #e5e7eb',
      borderRadius: '12px',
      boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
      fontSize: '14px',
      fontWeight: '500',
      padding: '16px 20px',
      maxWidth: '420px',
      minWidth: '300px',
      zIndex: 9999,
    },
    success: {
      style: {
        background: 'linear-gradient(135deg, #f0fdf4 0%, #ecfdf5 100%)',
        border: '1px solid #bbf7d0',
        color: '#166534',
        boxShadow: '0 20px 25px -5px rgba(34, 197, 94, 0.1), 0 10px 10px -5px rgba(34, 197, 94, 0.04)',
      },
      iconTheme: {
        primary: '#22c55e',
        secondary: '#f0fdf4',
      },
    },
    error: {
      style: {
        background: 'linear-gradient(135deg, #fef2f2 0%, #fef1f1 100%)',
        border: '1px solid #fecaca',
        color: '#dc2626',
        boxShadow: '0 20px 25px -5px rgba(239, 68, 68, 0.1), 0 10px 10px -5px rgba(239, 68, 68, 0.04)',
      },
      iconTheme: {
        primary: '#ef4444',
        secondary: '#fef2f2',
      },
    },
    loading: {
      style: {
        background: 'linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%)',
        border: '1px solid #bae6fd',
        color: '#0369a1',
        boxShadow: '0 20px 25px -5px rgba(59, 130, 246, 0.1), 0 10px 10px -5px rgba(59, 130, 246, 0.04)',
      },
      iconTheme: {
        primary: '#3b82f6',
        secondary: '#f0f9ff',
      },
    },
  },
};
