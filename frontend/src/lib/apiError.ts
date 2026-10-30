/**
 * The reason the API gives for a failed request, e.g. why the GoBD forbid a
 * deletion, so the user sees that instead of a generic error.
 */
export async function apiErrorMessage(response: Response, fallback: string): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body?.detail === 'string') return body.detail;
    if (typeof body?.error === 'string') return body.error;
  } catch {
    // not JSON
  }
  return fallback;
}
