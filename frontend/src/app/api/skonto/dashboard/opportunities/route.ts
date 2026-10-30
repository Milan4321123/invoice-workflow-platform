import { NextRequest, NextResponse } from 'next/server';
import { forwardAuth, unauthorized } from '@/lib/backendProxy';
import { getApiUrl } from '@/config/api';

export async function GET(request: NextRequest) {
  try {
    // Extract query parameters
    const { searchParams } = new URL(request.url);
    const queryParams = new URLSearchParams(searchParams);
    
    // Get backend URL with fallback
    const backendUrl = process.env.NEXT_PUBLIC_API_URL || process.env.INTERNAL_API_URL || 'http://localhost:8000';
    const apiUrl = `${backendUrl}/api/skonto/dashboard/opportunities?${queryParams.toString()}`;
    
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
      const errorData = await response.json();
      return NextResponse.json(errorData, { status: response.status });
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Skonto opportunities proxy error:', error);
    return NextResponse.json(
      { detail: 'Failed to fetch Skonto opportunities' },
      { status: 500 }
    );
  }
}
