import { NextRequest, NextResponse } from 'next/server';

/**
 * The backend requires a bearer token on every data route. Next.js API routes
 * run on the server, where the browser's token isn't available, so they pass
 * on the Authorization header of the request they are proxying.
 */
export function forwardAuth(request: NextRequest): Record<string, string> {
  const authorization = request.headers.get('authorization');
  return authorization ? { Authorization: authorization } : {};
}

/** Pass a backend 401 through as-is, so the browser sends the user to login instead of showing a 500. */
export function unauthorized(response: Response): NextResponse | null {
  if (response.status !== 401 && response.status !== 403) return null;
  return NextResponse.json({ detail: 'Authentication required' }, { status: 401 });
}
