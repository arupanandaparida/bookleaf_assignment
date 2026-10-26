import { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api } from '../api.js';
import { useLive } from '../useLive.js';
import { Empty, ErrorNote, StatusBadge, Thread, fmtDateTime } from '../components/ui.jsx';

function TicketView({ id, onChanged }) {
  const [ticket, setTicket] = useState(null);
  const [error, setError] = useState(null);
  const [body, setBody] = useState('');
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => api.ticket(id).then(setTicket).catch(setError), [id]);
  useEffect(() => { setTicket(null); load(); }, [load]);
  useLive((e) => { if (!e.ticketId || e.ticketId === Number(id)) load(); });

  async function send(e) {
    e.preventDefault();
    setBusy(true); setError(null);
    try { setTicket(await api.reply(id, body)); setBody(''); onChanged(); } catch (err) { setError(err); } finally { setBusy(false); }
  }

  if (error && !ticket) return <ErrorNote error={error} />;
  if (!ticket) return <p className="muted">Loading…</p>;
  const noReply = ticket.messages.every((m) => m.senderRole !== 'admin');
  return (
    <section className="card">
      <header className="row">
        <div><div className="muted small">{ticket.ref} · {ticket.book?.title || 'General / Account level'}</div><h2>{ticket.subject}</h2></div>
        <StatusBadge status={ticket.status} />
      </header>
      <Thread ticket={ticket} viewerRole="author" />
      {noReply && ticket.status !== 'Closed' && <p className="note">We have your message. A BookLeaf team member will reply here, and this page updates by itself.</p>}
      <ErrorNote error={error} />
      {ticket.status === 'Closed' ? <p className="muted">This ticket is closed. Please raise a new query if you need more help.</p> : (
        <form onSubmit={send} className="reply">
          <textarea rows={3} value={body} onChange={(e) => setBody(e.target.value)} placeholder={ticket.status === 'Resolved' ? 'Not fully solved? Reply to reopen this ticket.' : 'Add a follow-up'} required />
          <button className="btn primary" disabled={busy || body.trim().length < 2}>Send follow-up</button>
        </form>
      )}
    </section>
  );
}

export default function MyTickets() {
  const { id } = useParams();
  const [tickets, setTickets] = useState(null);
  const [error, setError] = useState(null);
  const load = useCallback(() => api.tickets().then((r) => setTickets(r.items)).catch(setError), []);
  useEffect(() => { load(); }, [load]);
  useLive(() => load()); // list refreshes on any event for this author's tickets

  if (error) return <ErrorNote error={error} />;
  if (!tickets) return <p className="muted">Loading your tickets…</p>;
  if (!tickets.length) return <Empty title="No tickets yet">Questions about royalties, ISBNs, printing or your book’s progress? <Link to="/tickets/new">Ask for help</Link>.</Empty>;

  return (
    <div className="split">
      <aside>
        <h1>My tickets</h1>
        <ul className="ticket-list">
          {tickets.map((t) => (
            <li key={t.id} className={String(t.id) === id ? 'selected' : ''}>
              <Link to={`/tickets/${t.id}`}>
                <div className="row"><strong>{t.subject}</strong><StatusBadge status={t.status} /></div>
                <div className="muted small">{t.ref} · {t.book?.title || 'General'} · {fmtDateTime(t.updatedAt)}</div>
              </Link>
            </li>
          ))}
        </ul>
      </aside>
      <div>{id ? <TicketView id={id} onChanged={load} /> : <Empty title="Select a ticket">Pick a ticket on the left to read the conversation.</Empty>}</div>
    </div>
  );
}
