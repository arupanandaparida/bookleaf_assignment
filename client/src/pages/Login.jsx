import { useState } from 'react';
import { useAuth } from '../auth.jsx';
import { ErrorNote } from '../components/ui.jsx';

const DEMO = [
  { label: 'Author: Ananya Reddy', email: 'ananya.reddy@email.com', password: 'Author@123' },
  { label: 'Author: Kavita Deshmukh (book in production)', email: 'kavita.deshmukh@email.com', password: 'Author@123' },
  { label: 'Admin: Ops lead', email: 'admin@bookleaf.com', password: 'Admin@123' },
];

export default function Login() {
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setBusy(true); setError(null);
    try { await login(email, password); } catch (err) { setError(err); } finally { setBusy(false); }
  }

  return (
    <div className="login-wrap">
      <form className="login card" onSubmit={submit}>
        <h1>BookLeaf</h1>
        <p className="muted">Sign in to your author or operations account.</p>
        <ErrorNote error={error} />
        <label>Email<input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus autoComplete="username" /></label>
        <label>Password<input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required autoComplete="current-password" /></label>
        <button className="btn primary" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button>
        <div className="demo">
          <div className="muted small">Demo accounts (click to fill)</div>
          {DEMO.map((d) => (
            <button type="button" key={d.email} className="link" onClick={() => { setEmail(d.email); setPassword(d.password); }}>{d.label}</button>
          ))}
        </div>
      </form>
    </div>
  );
}
