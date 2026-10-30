/**
 * fetch() with the logged-in user's bearer token.
 *
 * The backend rejects anonymous requests to every data route, so components
 * that call it (or the Next.js proxy routes in app/api) use this instead of
 * the global fetch. A 401 means the session ended: clear it and go to login.
 */
export async function authFetch(input: RequestInfo | URL, init: RequestInit = {}): Promise<Response> {
  const token = typeof window !== 'undefined' ? localStorage.getItem('authToken') : null;
  const headers = new Headers(init.headers);
  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  const response = await fetch(input, { ...init, headers });

  if (response.status === 401 && typeof window !== 'undefined') {
    localStorage.removeItem('authToken');
    localStorage.removeItem('authUser');
    if (window.location.pathname !== '/login') {
      window.location.href = '/login';
    }
  }
  return response;
}
