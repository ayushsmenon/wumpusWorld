import { Link, NavLink } from "react-router-dom";

export function AppShell({ children }) {
  return (
    <div className="home-shell">
      <header className="site-header">
        <Link className="brand" to="/" aria-label="Wumpus World home">
          <span className="brand-mark">W</span>
          <span>Wumpus World</span>
        </Link>
        <nav className="site-nav" aria-label="Primary navigation">
          <NavLink className="nav-link" to="/" end>
            Home
          </NavLink>
        </nav>
      </header>
      <main className="page-content">{children}</main>
    </div>
  );
}
