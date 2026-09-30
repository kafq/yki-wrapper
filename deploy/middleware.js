// Vercel Routing Middleware: one shared password for the whole site (HTTP Basic auth).
// Set it with:  vercel env add YKI_PASSWORD production
export const config = { matcher: '/:path*' };

export default function middleware(request) {
  const password = process.env.YKI_PASSWORD;
  if (!password) return new Response('YKI_PASSWORD is not set', { status: 500 });
  const header = request.headers.get('authorization') || '';
  if (header.startsWith('Basic ')) {
    let given = '';
    try { given = atob(header.slice(6)).split(':').slice(1).join(':'); } catch {}
    if (given === password) return new Response(null, { headers: { 'x-middleware-next': '1' } });
  }
  return new Response('Password required', {
    status: 401,
    headers: { 'WWW-Authenticate': 'Basic realm="YKI", charset="UTF-8"', 'Cache-Control': 'no-store' },
  });
}
