import { NextRequest, NextResponse } from 'next/server';
import { forwardAuth, unauthorized } from '@/lib/backendProxy';
import { getApiUrl } from '@/config/api';

export async function GET(request: NextRequest) {
  try {
    // Get backend URL with fallback
    const backendUrl = process.env.NEXT_PUBLIC_API_URL || process.env.INTERNAL_API_URL || 'http://localhost:8000';
    const apiUrl = `${backendUrl}/api/system-health`;
    
    const response = await fetch(apiUrl, {
      method: 'GET',
      headers: {
        ...forwardAuth(request),
        'Content-Type': 'application/json',
      },
    });

    const denied = unauthorized(response);
    if (denied) return denied;
    
    if (!response.ok) {
      throw new Error(`Backend responded with ${response.status}: ${response.statusText}`);
    }
    
    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('System health proxy error:', error);
    return NextResponse.json(
      { 
        status: 'error',
        error: error instanceof Error ? error.message : 'Unknown error',
        timestamp: new Date().toISOString()
      },
      { status: 500 }
    );
  }
}
