export const PRIORITY_CLASS = { Critical: 'p-critical', High: 'p-high', Medium: 'p-medium', Low: 'p-low' };
export const STATUS_CLASS = { Open: 's-open', 'In Progress': 's-progress', Resolved: 's-resolved', Closed: 's-closed' };

export const StatusBadge = ({ status }) => <span className={`badge ${STATUS_CLASS[status]}`}>{status}</span>;
export const PriorityBadge = ({ priority }) =>
  priority ? <span className={`badge ${PRIORITY_CLASS[priority]}`}>{priority}</span> : <span className="badge s-closed">Scoring…</span>;

export const inr = (n) => (n == null ? '–' : `₹${Number(n).toLocaleString('en-IN')}`);
export const fmtDate = (d) => (d ? new Date(d).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }) : '–');
export const fmtDateTime = (d) => new Date(d).toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' });

export function ageLabel(hours) {
  if (hours < 1) return 'just now';
  if (hours < 48) return `${hours}h`;
  return `${Math.round(hours / 24)}d`;
}

export const ErrorNote = ({ error }) => (error ? (
  <div className="alert error" role="alert">
    {error.message}
    {error.details?.length ? <ul>{error.details.map((d, i) => <li key={i}>{d.field ? `${d.field}: ` : ''}{d.message}</li>)}</ul> : null}
  </div>
) : null);

export const Empty = ({ title, children }) => (
  <div className="empty"><h3>{title}</h3><p>{children}</p></div>
);

/** Chronological conversation thread shared by both portals. */
export function Thread({ ticket, viewerRole }) {
  return (
    <div className="thread">
      <div className={`msg ${viewerRole === 'author' ? 'mine' : 'theirs'}`}>
        <div className="msg-meta">{ticket.author?.name || 'You'} · {fmtDateTime(ticket.createdAt)}</div>
        <p>{ticket.description}</p>
        {ticket.attachments?.length > 0 && <div className="muted small">Attached: {ticket.attachments.map((a) => a.name).join(', ')}</div>}
      </div>
      {ticket.messages.map((m) => (
        <div key={m.id} className={`msg ${m.senderRole === viewerRole ? 'mine' : 'theirs'} ${m.senderRole === 'admin' ? 'staff' : ''}`}>
          <div className="msg-meta">{m.senderName} · {fmtDateTime(m.createdAt)}</div>
          <p>{m.body}</p>
        </div>
      ))}
    </div>
  );
}
