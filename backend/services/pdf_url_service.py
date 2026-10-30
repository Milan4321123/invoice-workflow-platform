#!/usr/bin/env python3
"""
PDF URL Service - Centralized PDF URL construction
Handles both mock storage (for development) and Supabase storage (for production)
"""
import os
from typing import Optional

class PDFUrlService:
    """Service for constructing PDF URLs based on environment configuration"""
    
    def __init__(self):
        self.use_mock_storage = os.getenv("USE_MOCK_STORAGE", "false").lower() == "true"
        self.supabase_url = os.getenv("SUPA_URL")
        self.api_base_url = os.getenv("API_BASE_URL", "")
    
    def get_pdf_url(self, file_path: str, invoice_id: str = None) -> str:
        """
        Get PDF URL based on file path and environment configuration
        
        Args:
            file_path: The file path stored in database
            invoice_id: Optional invoice ID for secure API access
            
        Returns:
            Complete URL to access the PDF
        """
        if not file_path:
            return ""

        if os.getenv("DEMO_MODE", "false").lower() == "true":
            api_base = self.api_base_url or os.getenv("API_BASE_URL", "http://localhost:8000")
            return f"{api_base}/api/demo-files/{file_path}"
        
        # If we have invoice_id, use secure API endpoint
        if invoice_id:
            # Use backend URL, not frontend URL for PDF access
            api_base = self.api_base_url or os.getenv("API_BASE_URL", "http://localhost:8000")
            return f"{api_base}/api/pdf/view/{invoice_id}"
        
        if self.use_mock_storage:
            # Use mock storage for development/demo with full backend URL
            file_name = os.path.basename(file_path)
            api_base = self.api_base_url or os.getenv("API_BASE_URL", "http://localhost:8000")
            return f"{api_base}/api/mock-storage/{file_name}"
        else:
            # Use Supabase storage for production
            return self._construct_supabase_url(file_path)
    
    def _construct_supabase_url(self, file_path: str) -> str:
        """Construct Supabase storage URL with proper bucket logic"""
        # Determine the correct bucket based on file_path prefix
        if file_path.startswith('folder_watcher/'):
            bucket_name = "folderwatcher"
            file_name = file_path.replace('folder_watcher/', '')
        elif file_path.startswith('manual/'):
            bucket_name = "manual"
            file_name = file_path.replace('manual/', '')
        else:
            # Default for drag-drop uploads
            bucket_name = "invoices"
            file_name = file_path
        
        # Try to generate signed URL for private buckets
        try:
            from supabase import create_client
            supabase_service_key = os.getenv("SUPA_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
            
            if supabase_service_key and self.supabase_url:
                client = create_client(self.supabase_url, supabase_service_key)
                # Generate signed URL valid for 1 hour
                signed_url = client.storage.from_(bucket_name).create_signed_url(file_name, 3600)
                if signed_url and 'signedURL' in signed_url:
                    return signed_url['signedURL']
        except Exception as e:
            print(f"Warning: Could not generate signed URL for {file_path}: {e}")
        
        # Fallback to public URL (will work if bucket is public)
        return f"{self.supabase_url}/storage/v1/object/public/{bucket_name}/{file_name}"

# Global instance
pdf_url_service = PDFUrlService()