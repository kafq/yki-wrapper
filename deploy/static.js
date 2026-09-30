// Static mode for the hosted site: answers the player's /api/ calls in the browser.
// Index and translations come from pre-built JSON; saved words live in this browser (localStorage).
(() => {
  const realFetch = window.fetch.bind(window);
  const KEY = 'yki:words';
  let TR = null;
  const json = o => new Response(JSON.stringify(o), { headers: { 'Content-Type': 'application/json' } });
  const load = () => { try { return JSON.parse(localStorage.getItem(KEY) || '[]'); } catch (e) { return []; } };
  const store = w => { try { localStorage.setItem(KEY, JSON.stringify(w)); } catch (e) {} };
  const newId = () => Math.random().toString(16).slice(2, 12);
  const stamp = () => new Date().toISOString().slice(0, 16).replace('T', ' ');
  async function translate(keys) {
    if (!TR) TR = await (await realFetch('/data/translations.json')).json();
    const out = {}; for (const k of keys) out[k] = TR[k] || ''; return out;
  }
  window.fetch = async (input, opts = {}) => {
    const url = new URL(typeof input === 'string' ? input : input.url, location.href);
    const p = url.pathname, method = (opts.method || 'GET').toUpperCase();
    if (p === '/api/index' || p === '/api/reading' || p === '/api/writing') return realFetch('/data/' + p.slice(5) + '.json');
    if (p === '/api/translate') {
      const keys = method === 'POST' ? JSON.parse(opts.body || '[]') : (url.searchParams.get('w') || '').split(',').filter(Boolean);
      return json(await translate(keys));
    }
    if (p === '/api/words') {
      const w = load();
      if (method === 'GET') return json(w);
      if (method === 'POST') {
        const b = JSON.parse(opts.body || '{}'); const word = String(b.word || '').trim().toLowerCase();
        let e = w.find(x => x.word === word);
        if (!e) { e = { id: newId(), added: stamp(), word, display: b.display || '', translation: b.translation || '', context: b.context || '', source: b.source || '', time: +b.time || 0 }; w.push(e); store(w); }
        return json(e);
      }
      if (method === 'DELETE') { const id = url.searchParams.get('id'); store(w.filter(x => x.id !== id)); return json({ ok: true }); }
    }
    return realFetch(input, opts);
  };
  // CSV export without a server
  document.addEventListener('click', e => {
    const a = e.target.closest('a[href="/api/words.csv"]'); if (!a) return;
    e.preventDefault();
    const q = s => '"' + String(s ?? '').replace(/"/g, '""') + '"';
    const rows = [['word', 'translation', 'context', 'source', 'added'], ...load().map(x => [x.display || x.word, x.translation, x.context, x.source, x.added])];
    const blob = new Blob(['﻿' + rows.map(r => r.map(q).join(',')).join('\r\n')], { type: 'text/csv' });
    const link = document.createElement('a'); link.href = URL.createObjectURL(blob); link.download = 'yki-sanat.csv'; link.click();
    setTimeout(() => URL.revokeObjectURL(link.href), 1000);
  });
})();
