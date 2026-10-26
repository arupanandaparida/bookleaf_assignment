import { useEffect, useRef } from 'react';
import { getToken } from './api.js';

/**
 * Subscribes to server-sent ticket events and calls `onEvent` (latest callback, no resubscribe).
 * EventSource reconnects on its own; we also refetch when the tab becomes visible again so a
 * dropped connection never leaves stale data on screen.
 */
export function useLive(onEvent) {
  const ref = useRef(onEvent);
  ref.current = onEvent;

  useEffect(() => {
    const token = getToken();
    if (!token) return undefined;
    const es = new EventSource(`/api/events?token=${encodeURIComponent(token)}`);
    es.addEventListener('ticket', (e) => ref.current(JSON.parse(e.data)));
    es.onopen = () => ref.current({ type: 'reconnected' });
    const onVisible = () => document.visibilityState === 'visible' && ref.current({ type: 'visible' });
    document.addEventListener('visibilitychange', onVisible);
    return () => { es.close(); document.removeEventListener('visibilitychange', onVisible); };
  }, []);
}
