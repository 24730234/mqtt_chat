import React, { Suspense, lazy, useState } from 'react';
import App from './App.jsx';
const LiveApp = lazy(() => import('./live/LiveApp.jsx'));
export default function Root() {
  const [live, setLive] = useState(() => new URLSearchParams(location.search).get('mode') === 'live');
  function mode(value) { setLive(value); const url = new URL(location.href); value ? url.searchParams.set('mode', 'live') : url.searchParams.delete('mode'); history.replaceState(null, '', url); }
  return live ? <Suspense fallback={<div style={{ padding: 40 }}>Đang mở không gian kết nối…</div>}><LiveApp onDemo={() => mode(false)}/></Suspense> : <App onConnect={() => mode(true)}/>;
}
