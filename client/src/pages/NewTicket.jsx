import { useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { api } from '../api.js';
import { ErrorNote } from '../components/ui.jsx';

export default function NewTicket() {
  const nav = useNavigate();
  const [params] = useSearchParams();
  const [books, setBooks] = useState([]);
  const [bookId, setBookId] = useState(params.get('book') || '');
  const [subject, setSubject] = useState('');
  const [description, setDescription] = useState('');
  const [files, setFiles] = useState([]);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const fileRef = useRef();

  useEffect(() => { api.books().then((r) => setBooks(r.items)).catch(setError); }, []);

  async function submit(e) {
    e.preventDefault();
    setBusy(true); setError(null);
    try {
      // Attachments are UI-only per the brief: only file metadata is sent.
      const t = await api.createTicket({ bookId: bookId || null, subject, description, attachments: files.map((f) => ({ name: f.name, size: f.size })) });
      nav(`/tickets/${t.id}`);
    } catch (err) { setError(err); setBusy(false); }
  }

  return (
    <form className="card narrow" onSubmit={submit}>
      <h1>Ask for help</h1>
      <p className="muted">Tell us what is going on. Most replies arrive within one working day, and you will see them on this site as soon as we send them.</p>
      <ErrorNote error={error} />
      <label>Which book is this about?
        <select value={bookId} onChange={(e) => setBookId(e.target.value)}>
          <option value="">General / Account level</option>
          {books.map((b) => <option key={b.id} value={b.id}>{b.title}</option>)}
        </select>
      </label>
      <label>Subject<input value={subject} onChange={(e) => setSubject(e.target.value)} maxLength={150} required placeholder="e.g. Royalty for Q2 has not arrived" /></label>
      <label>What happened?
        <textarea rows={7} value={description} onChange={(e) => setDescription(e.target.value)} maxLength={5000} required
          placeholder="Include dates, amounts, platform names or order numbers if you have them." />
        <span className="muted small">{description.length}/5000</span>
      </label>
      <div>
        <input ref={fileRef} type="file" multiple hidden onChange={(e) => setFiles([...e.target.files].slice(0, 5))} />
        <button type="button" className="btn" onClick={() => fileRef.current.click()}>Attach photos or files</button>
        {files.length > 0 && <span className="muted small"> {files.map((f) => f.name).join(', ')}</span>}
        <div className="muted small">Optional. For print issues, photos of the copy help us verify faster. File names are recorded; upload storage is not enabled in this version.</div>
      </div>
      <button className="btn primary" disabled={busy}>{busy ? 'Sending…' : 'Send to BookLeaf'}</button>
    </form>
  );
}
