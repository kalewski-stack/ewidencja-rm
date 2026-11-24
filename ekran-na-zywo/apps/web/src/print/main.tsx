// Plansza z kodem QR do druku na stojak: A4 i A5, pion i poziom. Dane (kod) pobierane z tokenem operatora.
import { render } from 'preact';
import { useEffect, useState } from 'preact/hooks';
import { applyTheme, config } from '../lib/theme.ts';
import { takeToken } from '../lib/conn.ts';
import { t } from '../lib/i18n.ts';
import { Logos } from '../ui/common.tsx';
import '../themes/base.css';
import '../themes/print.css';

applyTheme();
const token = takeToken('t', 'opsToken');
const FORMATS = ['a4-portrait', 'a4-landscape', 'a5-portrait', 'a5-landscape'] as const;

function App() {
  const [svg, setSvg] = useState('');
  const [url, setUrl] = useState('');
  const [err, setErr] = useState('');
  const [fmt, setFmt] = useState<(typeof FORMATS)[number]>('a4-portrait');

  useEffect(() => {
    (async () => {
      try {
        const r = await fetch('/qr.svg', { headers: { Authorization: `Bearer ${token}` } });
        if (!r.ok) throw new Error();
        setSvg(URL.createObjectURL(await r.blob()));
      } catch { setErr(t('print.unauthorized')); }
    })();
    // Krótki adres pod kodem: ten sam, który jest zakodowany w QR (pochodzi z widoku operatora).
    const ws = new WebSocket(`${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}/ws?role=ops`);
    ws.onopen = () => ws.send(JSON.stringify({ t: 'hello', role: 'ops', token, preview: true }));
    ws.onmessage = (e) => { const m = JSON.parse(e.data); if (m.t === 'state') { setUrl(String(m.view.publicUrl).replace(/^https?:\/\//, '').replace(/\/$/, '')); ws.close(); } };
    return () => ws.close();
  }, []);

  useEffect(() => {
    const [size, orient] = fmt.split('-');
    let el = document.getElementById('page-size');
    if (!el) { el = document.createElement('style'); el.id = 'page-size'; document.head.appendChild(el); }
    el.textContent = `@page { size: ${size.toUpperCase()} ${orient}; margin: 0; }`;
  }, [fmt]);

  if (err) return <p class="print-err">{err}</p>;
  return (
    <>
      <div class="print-tools">
        {FORMATS.map((f) => <button class={fmt === f ? 'on' : ''} onClick={() => setFmt(f)}>{t(`print.${f}`)}</button>)}
        <button class="go" onClick={() => window.print()}>{t('print.print')}</button>
        <span>{t('print.hint')}</span>
      </div>
      <div class={`sheet ${fmt}`}>
        <div class="sheet-head"><Logos /></div>
        <div class="sheet-main">
          <div class="sheet-text">
            <h1>{t('print.title')}</h1>
            <p>{t('print.sub')}</p>
          </div>
          <div class="sheet-qr">
            {svg ? <img src={svg} alt={t('qr.alt')} /> : null}
            <p class="sheet-url">{url}</p>
          </div>
        </div>
        <div class="sheet-foot">{config.event.title}, {config.event.subtitle} · {config.event.place}, {config.event.date}</div>
      </div>
    </>
  );
}

render(<App />, document.getElementById('app')!);
