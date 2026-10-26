import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api } from '../api.js';
import { useLive } from '../useLive.js';
import { useAuth } from '../auth.jsx';
import { ErrorNote, PriorityBadge, StatusBadge, Thread, fmtDateTime } from '../components/ui.jsx';

export default function AdminTicket() {
  const { id } = useParams();
  const { user } = useAuth();
  const [ticket, setTicket] = useState(null);
  const [meta, setMeta] = useState(null);
  const [error, setError] = useState(null);

  const [reply, setReply] = useState('');
  const [draftInfo, setDraftInfo] = useState(null); // {source, loading}
  const [afterStatus, setAfterStatus] = useState('In Progress');
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const replyTouched = useRef(false);

  const load = useCallback(() => api.ticket(id).then(setTicket).catch(setError), [id]);

  const loadDraft = useCallback(async (regenerate = false) => {
    setDraftInfo({ loading: true });
    try {
      const { draft } = await api.draft(id, regenerate);
      setDraftInfo({ source: draft.source });
      // Never overwrite text the admin has started typing unless they explicitly asked to regenerate.
      if (regenerate || !replyTouched.current) { setReply(draft.text); replyTouched.current = false; }
    } catch (e) { setDraftInfo({ error: e.message }); }
  }, [id]);

  useEffect(() => { api.meta().then(setMeta); }, []);
  useEffect(() => { replyTouched.current = false; setReply(''); setTicket(null); load(); loadDraft(false); }, [id]); // eslint-disable-line react-hooks/exhaustive-deps
  useLive((e) => { if (!e.ticketId || e.ticketId === Number(id)) load(); });

  const run = async (fn) => { setBusy(true); setError(null); try { setTicket(await fn()); } catch (e) { setError(e); } finally { setBusy(false); } };
  const patch = (p) => run(() => api.updateTicket(id, p));

  async function send(e) {
    e.preventDefault();
    await run(() => api.reply(id, reply, afterStatus));
    setReply(''); replyTouched.current = false; setDraftInfo(null);
  }

  if (error && !ticket) return <ErrorNote error={error} />;
  if (!ticket || !meta) return <p className="muted">Loading ticket…</p>;
  const staleDraft = ticket.aiDraft?.stale && ticket.messages.length > 0 && ticket.messages.at(-1).senderRole === 'author';

  return (
    <>
      <Link className="link small" to="/admin">← Back to queue</Link>
      <div className="detail">
        <section className="card">
          <header className="row">
            <div>
              <div className="muted small">{ticket.ref} · {ticket.author.name} ({ticket.author.email}) · {ticket.book ? `${ticket.book.title} (${ticket.bookStatus})` : 'General / Account level'}</div>
              <h2>{ticket.subject}</h2>
            </div>
            <div className="badges"><PriorityBadge priority={ticket.priority} /><StatusBadge status={ticket.status} /></div>
          </header>
          <Thread ticket={ticket} viewerRole="admin" />
          <ErrorNote error={error} />

          <form onSubmit={send} className="composer">
            <div className="row">
              <h3>Reply to author</h3>
              <div className="draft-actions">
                {draftInfo?.loading && <span className="muted small">Drafting with AI…</span>}
                {draftInfo?.source === 'ai' && <span className="tag ai">AI draft, review before sending</span>}
                {draftInfo?.source === 'template' && <span className="tag warn">AI unavailable: template loaded</span>}
                <button type="button" className="link" disabled={draftInfo?.loading} onClick={() => loadDraft(true)}>Regenerate draft</button>
              </div>
            </div>
            {staleDraft && <p className="note">The author replied after this draft was written. Regenerate to include their latest message.</p>}
            {draftInfo?.error && <p className="note">Could not load a draft ({draftInfo.error}). You can write the reply manually.</p>}
            <textarea rows={11} value={reply} placeholder={draftInfo?.loading ? 'Generating a draft from the knowledge base…' : 'Write your reply'}
              onChange={(e) => { replyTouched.current = true; setReply(e.target.value); }} required />
            <div className="row">
              <label className="inline">After sending, set status to
                <select value={afterStatus} onChange={(e) => setAfterStatus(e.target.value)}>{['In Progress', 'Resolved', 'Closed'].map((s) => <option key={s}>{s}</option>)}</select>
              </label>
              <button className="btn primary" disabled={busy || reply.trim().length < 2}>Send reply</button>
            </div>
          </form>
        </section>

        <aside className="side">
          <section className="card">
            <h3>Triage</h3>
            <label>Status<select value={ticket.status} onChange={(e) => patch({ status: e.target.value })}>{meta.statuses.map((s) => <option key={s}>{s}</option>)}</select></label>
            <label>Category {ticket.categorySource === 'ai' && <span className="tag ai">AI</span>}{ticket.categorySource === 'rules' && <span className="tag warn">rules</span>}{ticket.categorySource === 'admin' && <span className="tag">edited</span>}
              <select value={ticket.category || ''} onChange={(e) => patch({ category: e.target.value })}>
                {!ticket.category && <option value="">Classifying…</option>}{meta.categories.map((c) => <option key={c}>{c}</option>)}
              </select>
            </label>
            <label>Priority {ticket.prioritySource === 'ai' && <span className="tag ai">AI</span>}{ticket.prioritySource === 'rules' && <span className="tag warn">rules</span>}{ticket.prioritySource === 'admin' && <span className="tag">edited</span>}
              <select value={ticket.priority || ''} onChange={(e) => patch({ priority: e.target.value })}>
                {!ticket.priority && <option value="">Scoring…</option>}{meta.priorities.map((p) => <option key={p}>{p}</option>)}
              </select>
            </label>
            {ticket.aiReasoning && <p className="muted small">Why: {ticket.aiReasoning}</p>}
            <div className="row">
              <span className="small">Assigned to <b>{ticket.assignedTo?.name || 'nobody'}</b></span>
              {ticket.assignedTo?.id === user.id
                ? <button className="link" onClick={() => patch({ assignedTo: null })}>Unassign</button>
                : <button className="btn" onClick={() => patch({ assignedTo: 'me' })}>Assign to me</button>}
            </div>
            <button className="link" disabled={busy} onClick={() => run(() => api.reclassify(id))}>Re-run AI classification</button>
          </section>

          <section className="card">
            <h3>Internal notes</h3>
            <p className="muted small">Only visible to BookLeaf staff.</p>
            <ul className="notes">
              {ticket.notes.map((n) => <li key={n.id}><div className="muted small">{n.adminName} · {fmtDateTime(n.createdAt)}</div>{n.body}</li>)}
              {!ticket.notes.length && <li className="muted small">No notes yet.</li>}
            </ul>
            <form onSubmit={(e) => { e.preventDefault(); run(() => api.addNote(id, note)).then(() => setNote('')); }}>
              <textarea rows={3} value={note} onChange={(e) => setNote(e.target.value)} placeholder="e.g. Verified bank details with finance" />
              <button className="btn" disabled={busy || !note.trim()}>Add note</button>
            </form>
          </section>
        </aside>
      </div>
    </>
  );
}
