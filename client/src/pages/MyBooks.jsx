import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api.js';
import { Empty, ErrorNote, fmtDate, inr } from '../components/ui.jsx';

function Book({ b }) {
  return (
    <article className="card book">
      <header>
        <div>
          <h2>{b.title}</h2>
          <div className="muted small">{b.genre}</div>
        </div>
        <span className={`badge ${b.inProduction ? 's-progress' : 's-resolved'}`}>{b.status}</span>
      </header>

      <dl className="facts">
        <div><dt>ISBN</dt><dd>{b.isbn || '–'}</dd></div>
        <div><dt>Published</dt><dd>{b.inProduction ? 'Not yet' : fmtDate(b.publicationDate)}</dd></div>
        <div><dt>MRP</dt><dd>{b.mrp ? inr(b.mrp) : 'Set at publication'}</dd></div>
        <div><dt>Copies sold</dt><dd>{b.copiesSold.toLocaleString('en-IN')}</dd></div>
      </dl>

      {b.inProduction ? (
        <p className="note">Your book is in production, so there are no sales or royalties yet. We email you at every stage.</p>
      ) : (
        <>
          <dl className="money">
            <div><dt>Royalty earned</dt><dd>{inr(b.royaltyEarned)}</dd></div>
            <div><dt>Paid</dt><dd>{inr(b.royaltyPaid)}</dd></div>
            <div className={b.royaltyPending > 0 ? 'pending' : ''}><dt>Pending</dt><dd>{inr(b.royaltyPending)}</dd></div>
          </dl>
          {b.belowPayoutThreshold && <p className="note">Pending royalty is under the ₹1,000 minimum payout, so it rolls over to the next quarter.</p>}
          {b.royaltyPaid === 0 && b.royaltyPending >= 1000 && <p className="note">No payout yet. Royalties are paid by bank transfer within 45 days of each quarter ending.</p>}
          <div className="muted small">
            Last payout: {b.lastPayoutDate ? fmtDate(b.lastPayoutDate) : 'none yet'} · Printed by {b.printPartner} · On {b.availableOn.join(', ')}
          </div>
        </>
      )}
      <Link className="link small" to={`/tickets/new?book=${b.id}`}>Ask about this book</Link>
    </article>
  );
}

export default function MyBooks() {
  const [books, setBooks] = useState(null);
  const [error, setError] = useState(null);
  useEffect(() => { api.books().then((r) => setBooks(r.items)).catch(setError); }, []);

  if (error) return <ErrorNote error={error} />;
  if (!books) return <p className="muted">Loading your books…</p>;
  if (!books.length) return <Empty title="No books yet">Once your manuscript is received it will appear here.</Empty>;

  const totals = books.reduce((t, b) => ({ earned: t.earned + b.royaltyEarned, paid: t.paid + b.royaltyPaid, pending: t.pending + b.royaltyPending }), { earned: 0, paid: 0, pending: 0 });
  return (
    <>
      <h1>My books</h1>
      <p className="muted">Across all titles you have earned {inr(totals.earned)}: {inr(totals.paid)} paid and {inr(totals.pending)} pending.</p>
      <div className="grid">{books.map((b) => <Book key={b.id} b={b} />)}</div>
    </>
  );
}
