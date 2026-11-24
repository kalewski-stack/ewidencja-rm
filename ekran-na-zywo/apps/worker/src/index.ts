// Worker: routing, limity per IP, autoryzacja tokenami. Cała logika wydarzenia siedzi w Durable Object (room.ts).
import { qrSvg } from '../../../packages/shared/qr.ts';
import config from '../../../content/config.json';
import { EventRoom } from './room.ts';
import { safeEqual, json, bearer } from './http.ts';

export { EventRoom };

export interface Env {
  ASSETS: Fetcher;
  EVENT: DurableObjectNamespace<EventRoom>;
  BACKUP?: R2Bucket;
  PUBLIC_URL: string;
  EVENT_ID: string;
  OPS_TOKEN: string;
  MOD_TOKEN: string;
  SCREEN_KEY: string;
  SALT: string;
}

// Limit per IP jest celowo szeroki (6000/min): cała sala siedzi za jednym NAT-em hotelowego Wi-Fi,
// a telefony bez WebSocket odpytują stan co 2 s (120 telefonów = 3600 żądań na minutę).
// Licznik żyje tylko w pamięci izolatu, adresów IP nigdzie nie zapisujemy i nikogo nie blokujemy na stałe.
const ipHits = new Map<string, { n: number; reset: number }>();
function ipLimited(ip: string): boolean {
  const now = Date.now();
  const max = config.limits.ipRequestsPerMinute;
  let e = ipHits.get(ip);
  if (!e || e.reset < now) { e = { n: 0, reset: now + 60_000 }; ipHits.set(ip, e); }
  if (ipHits.size > 5000) for (const [k, v] of ipHits) if (v.reset < now) ipHits.delete(k);
  return ++e.n > max;
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    const path = url.pathname;

    if (path === '/health' || path === '/ws' || path.startsWith('/api/')) {
      if (path.startsWith('/api/') && ipLimited(request.headers.get('CF-Connecting-IP') ?? 'local')) {
        return json({ ok: false, code: 'rate_limited', message: 'Za dużo żądań. Spróbuj za chwilę.' }, 429, { 'Retry-After': '20' });
      }
      const room = env.EVENT.get(env.EVENT.idFromName(env.EVENT_ID || 'event'));
      return room.fetch(request);
    }

    if (path === '/qr.svg') {
      const tok = bearer(request);
      if (!tok || !(safeEqual(tok, env.OPS_TOKEN) || safeEqual(tok, env.MOD_TOKEN))) {
        return json({ ok: false, code: 'unauthorized', message: 'Brak dostępu.' }, 401);
      }
      return new Response(qrSvg(env.PUBLIC_URL), {
        headers: { 'Content-Type': 'image/svg+xml; charset=utf-8', 'Cache-Control': 'no-store', 'X-Robots-Tag': 'noindex' },
      });
    }

    // Bezpośrednie wejścia do testów: ta sama strona telefonu, tryb wymuszony po stronie klienta.
    if (path === '/ankieta' || path === '/pytania') {
      return env.ASSETS.fetch(new Request(new URL('/', url), request));
    }

    return env.ASSETS.fetch(request);
  },
} satisfies ExportedHandler<Env>;
