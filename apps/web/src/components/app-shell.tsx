import { NavLink, Outlet } from "react-router-dom";

export function BrandMark() {
  return (
    <span className="brand-mark" aria-hidden="true">
      <span />
      <span />
    </span>
  );
}

export function AppShell() {
  return (
    <div className="app-frame">
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <header className="site-header">
        <NavLink className="brand" to="/" aria-label="Mori home">
          <BrandMark />
          <span className="brand-copy">
            <strong>Mori</strong>
            <small>Mandarin studio</small>
          </span>
        </NavLink>

        <nav className="main-nav" aria-label="Primary navigation">
          <NavLink to="/" end>
            <span aria-hidden="true">01</span>
            Study desk
          </NavLink>
          <NavLink to="/memories">
            <span aria-hidden="true">02</span>
            Learner file
          </NavLink>
        </nav>

        <NavLink
          className="learner-chip"
          to="/profile"
          aria-label="Open Jason Tan's profile"
        >
          <span className="avatar" aria-hidden="true">
            JT
          </span>
          <span>
            <small>Student</small>
            <strong>Jason Tan</strong>
          </span>
        </NavLink>
      </header>

      <main id="main-content" className="page-shell">
        <Outlet />
      </main>

      <footer className="site-footer">
        <span>Mori Mandarin Studio</span>
        <span>Practice with patience · Speak with confidence</span>
      </footer>
    </div>
  );
}
