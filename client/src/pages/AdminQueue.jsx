import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api.js';
import { useLive } from '../useLive.js';
import { Empty, ErrorNote, PriorityBadge, StatusBadge, ageLabel } from '../components/ui.jsx';

const EMPTY = { status: '', category: '', priority: '', assigned: '', from: '', to: '', q: '' };

export default function AdminQueue() {
  const [meta, setMeta] = useState(null);
  const [filters, setFilters] = useState({ ...EMPTY, status: '' });
  const [data, setData] = useState(null);
  const [stats, setStats] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => { api.meta().then(setMeta).catch(setError); }, []);
  const load = useCallback(() => {
    api.tickets(filters).then(setData).catch(setError);
    api.stats().then(setStats).catch(() => {});
  }, [filters]);
  useEffect(() => { load(); }, [load]);
  useLive(() => load());

  const set = (k) => (e) => setFilters((f) => ({ ...f, [k]: e.target.value }));

  return (
    <>
      <h1>Ticket queue</h1>
      {stats && (
        <div className="stats">
          <div><b>{stats.tickets.open}</b><span>Open</span></div>
          <div><b>{stats.tickets.inProgress}</b><span>In progress</span></div>
          <div className={stats.tickets.critical ? 'hot' : ''}><b>{stats.tickets.critical}</b><span>Critical</span></div>
          <div><b>{stats.tickets.unassigned}</b><span>Unassigned</span></div>
          <div className={stats.tickets.overdue ? 'hot' : ''}><b>{stats.tickets.overdue}</b><span>Waiting over 48h</span></div>
          <div className="ai-stat">
            <b>{stats.ai.configured ? (stats.ai.circuitOpen ? 'Paused' : 'On') : 'Off'}</b>
            <span>AI · {stats.ai.calls} calls · {(stats.ai.inputTokens + stats.ai.outputTokens).toLocaleString()} tokens{stats.ai.failures ? ` · ${stats.ai.failures} failed` : ''}</span>
          </div>
        </div>
      )}

      <div className="filters card">
        <input placeholder="Search subject, text or author" value={filters.q} onChange={set('q')} />
        <select value={filters.status} onChange={set('status')}><option value="">All statuses</option>{meta?.statuses.map((s) => <option key={s}>{s}</option>)}</select>
        <select value={filters.category} onChange={set('category')}><option value="">All categories</option>{meta?.categories.map((s) => <option key={s}>{s}</option>)}</select>
        <select value={filters.priority} onChange={set('priority')}><option value="">All priorities</option>{meta?.priorities.map((s) => <option key={s}>{s}</option>)}</select>
        <select value={filters.assigned} onChange={set('assigned')}><option value="">Any assignee</option><option value="me">Assigned to me</option><option value="unassigned">Unassigned</option></select>
        <label className="inline">From<input type="date" value={filters.from} onChange={set('from')} /></label>
        <label className="inline">To<input type="date" value={filters.to} onChange={set('to')} /></label>
        <button className="link" onClick={() => setFilters(EMPTY)}>Clear</button>
      </div>

      <ErrorNote error={error} />
      {!data ? <p className="muted">Loading tickets…</p> : !data.items.length ? (
        <Empty title="Nothing matches">Try clearing a filter. New author tickets appear here automatically.</Empty>
      ) : (
        <div className="table-wrap">
          <table className="queue">
            <thead><tr><th>Priority</th><th>Ticket</th><th>Author</th><th>Category</th><th>Status</th><th>Assignee</th><th>Age</th></tr></thead>
            <tbody>
              {data.items.map((t) => (
                <tr key={t.id} className={`${t.isOverdue ? 'overdue' : ''} ${['Resolved', 'Closed'].includes(t.status) ? 'done' : ''}`}>
                  <td><PriorityBadge priority={t.priority} /></td>
                  <td>
                    <Link to={`/admin/tickets/${t.id}`}><strong>{t.subject}</strong></Link>
                    <div className="muted small">{t.ref} · {t.book?.title || 'General / Account'}</div>
                  </td>
                  <td>{t.author.name}</td>
                  <td>{t.category || <span className="muted">Classifying…</span>}{t.categorySource === 'admin' && <span className="tag">edited</span>}{t.categorySource === 'rules' && <span className="tag" title="AI unavailable; classified by keyword rules">rules</span>}</td>
                  <td><StatusBadge status={t.status} /></td>
                  <td>{t.assignedTo?.name || <span className="muted">Unassigned</span>}</td>
                  <td className={t.isOverdue ? 'age hot' : 'age'}>{ageLabel(t.ageHours)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {data && <p className="muted small">{data.total} ticket{data.total === 1 ? '' : 's'} · sorted by urgency, then oldest first</p>}
    </>
  );
}
