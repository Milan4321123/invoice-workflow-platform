import { NextRequest, NextResponse } from 'next/server';
import { forwardAuth, unauthorized } from '@/lib/backendProxy';
import { getApiUrl } from '@/config/api';

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const resolvedParams = await params;
    const invoiceId = resolvedParams.id;

    // Basic validation
    if (!invoiceId || invoiceId.trim() === '') {
      return NextResponse.json(
        { error: 'Invalid invoice ID' },
        { status: 400 }
      );
    }

    // TODO: Replace with actual validation logic
    // For now, we'll do a simple check against the backend
    const backendUrl = getApiUrl();
    const response = await fetch(`${backendUrl}/api/invoices/${invoiceId}/validate`, {
      method: 'GET',
      headers: {
        ...forwardAuth(request),
        'Content-Type': 'application/json',
      },
    });

    const denied = unauthorized(response);
    if (denied) return denied;

    if (response.status === 404) {
      return NextResponse.json(
        { error: 'Invoice not found' },
        { status: 404 }
      );
    }

    if (!response.ok) {
      throw new Error(`Backend API error: ${response.statusText}`);
    }

    const data = await response.json();
    return NextResponse.json({ valid: true, ...data });

  } catch (error) {
    console.error('Error validating invoice:', error);
    return NextResponse.json(
      { error: 'Failed to validate invoice' },
      { status: 500 }
    );
  }
}
