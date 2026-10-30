import { NextRequest, NextResponse } from 'next/server';
import { forwardAuth, unauthorized } from '@/lib/backendProxy';
import { getApiUrl } from '@/config/api';

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id: invoiceId } = await params;

    // Proxy to backend API
    const backendUrl = getApiUrl();
    const response = await fetch(`${backendUrl}/api/invoices/${invoiceId}/editor`, {
      method: 'GET',
      headers: {
        ...forwardAuth(request),
        'Content-Type': 'application/json',
      },
    });

    const denied = unauthorized(response);
    if (denied) return denied;

    if (!response.ok) {
      if (response.status === 404) {
        return NextResponse.json(
          { error: 'Invoice not found' },
          { status: 404 }
        );
      }
      throw new Error(`Backend API error: ${response.statusText}`);
    }

    const data = await response.json();
    return NextResponse.json(data);

  } catch (error) {
    console.error('Error fetching invoice data:', error);
    return NextResponse.json(
      { error: 'Failed to fetch invoice data' },
      { status: 500 }
    );
  }
}

export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id: invoiceId } = await params;
    const body = await request.json();

    // Proxy to backend API
    const backendUrl = getApiUrl();
    const response = await fetch(`${backendUrl}/api/invoices/${invoiceId}/editor`, {
      method: 'PUT',
      headers: {
        ...forwardAuth(request),
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    });

    const denied = unauthorized(response);
    if (denied) return denied;

    if (!response.ok) {
      if (response.status === 404) {
        return NextResponse.json(
          { error: 'Invoice not found' },
          { status: 404 }
        );
      }
      throw new Error(`Backend API error: ${response.statusText}`);
    }

    const data = await response.json();
    return NextResponse.json(data);

  } catch (error) {
    console.error('Error updating invoice data:', error);
    return NextResponse.json(
      { error: 'Failed to update invoice data' },
      { status: 500 }
    );
  }
}
