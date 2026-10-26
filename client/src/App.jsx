import { Navigate, NavLink, Outlet, Route, Routes } from 'react-router-dom';
import { useAuth } from './auth.jsx';
import Login from './pages/Login.jsx';
import MyBooks from './pages/MyBooks.jsx';
import NewTicket from './pages/NewTicket.jsx';
import MyTickets from './pages/MyTickets.jsx';
import AdminQueue from './pages/AdminQueue.jsx';
import AdminTicket from './pages/AdminTicket.jsx';

function Shell() {
  const { user, logout } = useAuth();
  const links = user.role === 'admin'
    ? [['/admin', 'Ticket queue']]
    : [['/books', 'My books'], ['/tickets/new', 'Ask for help'], ['/tickets', 'My tickets']];
  return (
    <>
      <header className="topbar">
        <div className="brand">BookLeaf <span>{user.role === 'admin' ? 'Operations' : 'Author support'}</span></div>
        <nav>{links.map(([to, label]) => <NavLink key={to} to={to} end className={({ isActive }) => (isActive ? 'active' : '')}>{label}</NavLink>)}</nav>
        <div className="who">{user.name}<button className="link" onClick={logout}>Sign out</button></div>
      </header>
      <main className="page"><Outlet /></main>
    </>
  );
}

/** Gate a route tree by login state and role; wrong-role users are bounced to their own home. */
function Protected({ role }) {
  const { user, loading } = useAuth();
  if (loading) return <p className="muted pad">Loading…</p>;
  if (!user) return <Navigate to="/login" replace />;
  if (user.role !== role) return <Navigate to={user.role === 'admin' ? '/admin' : '/books'} replace />;
  return <Shell />;
}

export default function App() {
  const { user } = useAuth();
  const home = user ? (user.role === 'admin' ? '/admin' : '/books') : '/login';
  return (
    <Routes>
      <Route path="/login" element={user ? <Navigate to={home} replace /> : <Login />} />
      <Route element={<Protected role="author" />}>
        <Route path="/books" element={<MyBooks />} />
        <Route path="/tickets/new" element={<NewTicket />} />
        <Route path="/tickets" element={<MyTickets />} />
        <Route path="/tickets/:id" element={<MyTickets />} />
      </Route>
      <Route element={<Protected role="admin" />}>
        <Route path="/admin" element={<AdminQueue />} />
        <Route path="/admin/tickets/:id" element={<AdminTicket />} />
      </Route>
      <Route path="*" element={<Navigate to={home} replace />} />
    </Routes>
  );
}
