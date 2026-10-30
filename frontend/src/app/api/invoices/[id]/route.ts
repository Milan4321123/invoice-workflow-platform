import { NextRequest, NextResponse } from 'next/server';
import { forwardAuth, unauthorized } from '@/lib/backendProxy';
import { getApiUrl } from '@/config/api';

export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const updateData = await request.json();
    
    const apiUrl = getApiUrl();
    
    const response = await fetch(`${apiUrl}/api/invoices/${id}`, {
      method: 'PUT',
      headers: {
        ...forwardAuth(request),
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(updateData),
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
    console.error('Update invoice proxy error:', error);
    return NextResponse.json(
      { error: 'Failed to update invoice' },
      { status: 500 }
    );
  }
}
