import { Link, NavLink, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { useEffect, useRef, useState } from "react";
import Logo from "./components/Logo";
import { useAuth } from "./auth";
import Landing from "./pages/Landing";
import PublicDemo from "./pages/PublicDemo";
import SuperAdminConsole from "./pages/SuperAdminConsole";
import IncidentRoom from "./pages/IncidentRoom";
import Login from "./pages/Login";
import Signup from "./pages/Signup";
import Profile from "./pages/Profile";
import { AgentsPage, FaqPage, SecurityPage } from "./pages/SitePages";

// Public nav — Admin is NOT listed here; it appears only when admin key is active
const NAV = [
  { to: "/agents", label: "Agents" },
  { to: "/security", label: "Security" },
  { to: "/demo", label: "Live demo" },
  { to: "/faq", label: "FAQ" },
];

function ScrollToTop() {
  const { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);
  return null;
}

function AnnouncementBar() {
  return (
    <div className="flex flex-wrap items-center justify-center gap-x-4 gap-y-1 bg-gradient-to-r from-brand-deep via-brand to-brand-deep px-4 py-2 text-center text-[13px] font-semibold text-white">
      <span>New: every deploy now needs a one-time approval that mints a 15-minute AWS session.</span>
      <Link to="/security" className="underline underline-offset-4 hover:text-mint">
        See how it works
      </Link>
    </div>
  );
}

// ── Profile dropdown (shown when user is signed in) ───────────────────────────
function ProfileDropdown({ user, hasAdminKey, onLogout }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  const { pathname } = useLocation();

  // Close on route change
  useEffect(() => setOpen(false), [pathname]);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    function handleOutside(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener("mousedown", handleOutside);
    return () => document.removeEventListener("mousedown", handleOutside);
  }, [open]);

  const initials = user.name
    .trim()
    .split(" ")
    .map((w) => w[0]?.toUpperCase() || "")
    .slice(0, 2)
    .join("");

  return (
    <div className="relative" ref={ref}>
      {/* Avatar button */}
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-haspopup="true"
        aria-label={`Profile menu for ${user.name}`}
        className="flex h-9 w-9 items-center justify-center rounded-full bg-brand/20 text-sm font-extrabold text-brand ring-2 ring-transparent transition hover:ring-brand/40"
      >
        {initials}
      </button>

      {/* Dropdown panel */}
      {open && (
        <div className="absolute right-0 top-11 z-50 w-64 overflow-hidden rounded-2xl border border-line bg-panel shadow-xl shadow-black/40">
          {/* User info header */}
          <div className="border-b border-line px-4 py-4">
            <div className="flex items-center gap-3">
              <span className="flex h-11 w-11 flex-none items-center justify-center rounded-full bg-brand/20 text-base font-extrabold text-brand">
                {initials}
              </span>
              <div className="min-w-0">
                <p className="truncate font-bold">{user.name}</p>
                <p className="truncate text-xs text-mute">{user.email}</p>
              </div>
            </div>
          </div>

          {/* Menu items */}
          <div className="p-2">
            <Link
              to="/profile"
              onClick={() => setOpen(false)}
              className="flex items-center gap-2.5 rounded-xl px-3 py-2.5 text-sm font-semibold transition-colors hover:bg-panel-2"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
                <circle cx="12" cy="8" r="4" />
                <path d="M4 20c0-4 3.6-7 8-7s8 3 8 7" />
              </svg>
              View profile
            </Link>

            {hasAdminKey && (
              <Link
                to="/console"
                onClick={() => setOpen(false)}
                className="flex items-center gap-2.5 rounded-xl px-3 py-2.5 text-sm font-semibold text-mint transition-colors hover:bg-panel-2"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
                  <rect x="2" y="3" width="20" height="14" rx="2" />
                  <path d="M8 21h8M12 17v4" />
                </svg>
                Admin console
              </Link>
            )}
          </div>

          {/* Logout */}
          <div className="border-t border-line p-2">
            <button
              type="button"
              onClick={() => { setOpen(false); onLogout(); }}
              className="flex w-full items-center gap-2.5 rounded-xl px-3 py-2.5 text-sm font-semibold text-heat transition-colors hover:bg-heat/10"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                <polyline points="16 17 21 12 16 7" />
                <line x1="21" y1="12" x2="9" y2="12" />
              </svg>
              Log out
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Header ────────────────────────────────────────────────────────────────────
function Header() {
  const { user, signOut, hasAdminKey } = useAuth();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => setMobileOpen(false), [pathname]);

  const link = ({ isActive }) =>
    `rounded-full px-4 py-2 text-sm font-semibold transition-colors ${
      isActive ? "bg-brand/15 text-mint" : "text-mute hover:text-paper"
    }`;

  function logout() {
    signOut();
    navigate("/");
  }

  return (
    <header className="sticky top-0 z-40 border-b border-line/70 bg-ink/80 backdrop-blur-xl">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-6 py-3.5">
        {/* Logo */}
        <NavLink to="/" aria-label="ShadowFix home">
          <Logo />
        </NavLink>

        {/* Desktop nav */}
        <nav className="hidden items-center gap-1 md:flex" aria-label="Main">
          {NAV.map((item) => (
            <NavLink key={item.to} to={item.to} className={link}>
              {item.label}
            </NavLink>
          ))}
          {/* Admin link — only visible when admin key is set */}
          {hasAdminKey && (
            <NavLink to="/console" className={link}>
              Admin
            </NavLink>
          )}
        </nav>

        {/* Right side */}
        <div className="flex items-center gap-2.5">
          {user ? (
            // Signed-in: show profile avatar dropdown
            <ProfileDropdown user={user} hasAdminKey={hasAdminKey} onLogout={logout} />
          ) : (
            // Not signed in: show Login / Signup
            <>
              <NavLink
                to="/login"
                className="hidden rounded-full border border-line px-4 py-2 text-sm font-semibold text-paper transition-colors hover:border-brand sm:block"
              >
                Log in
              </NavLink>
              <NavLink
                to="/signup"
                className="rounded-full bg-brand px-4 py-2 text-sm font-bold text-white shadow-[0_0_28px_-6px_var(--color-brand)] transition-colors hover:bg-brand-deep"
              >
                Sign up
              </NavLink>
            </>
          )}

          {/* Mobile hamburger */}
          <button
            type="button"
            onClick={() => setMobileOpen((v) => !v)}
            aria-expanded={mobileOpen}
            aria-controls="mobile-nav"
            aria-label="Menu"
            className="flex h-9 w-9 items-center justify-center rounded-full border border-line md:hidden"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
              {mobileOpen ? (
                <path d="M6 6l12 12M18 6L6 18" />
              ) : (
                <path d="M4 7h16M4 12h16M4 17h16" />
              )}
            </svg>
          </button>
        </div>
      </div>

      {/* Mobile nav */}
      {mobileOpen && (
        <nav id="mobile-nav" className="border-t border-line px-6 py-4 md:hidden" aria-label="Mobile">
          <div className="flex flex-col gap-1">
            {NAV.map((item) => (
              <NavLink key={item.to} to={item.to} className={link}>
                {item.label}
              </NavLink>
            ))}
            {hasAdminKey && (
              <NavLink to="/console" className={link}>Admin</NavLink>
            )}
            {user ? (
              <>
                <NavLink to="/profile" className={link}>
                  Profile — {user.name}
                </NavLink>
                <button
                  type="button"
                  onClick={logout}
                  className="rounded-full px-4 py-2 text-left text-sm font-semibold text-heat hover:bg-heat/10"
                >
                  Log out
                </button>
              </>
            ) : (
              <>
                <NavLink to="/login" className={link}>Log in</NavLink>
                <NavLink to="/signup" className={link}>Sign up</NavLink>
              </>
            )}
          </div>
        </nav>
      )}
    </header>
  );
}

// ── Footer ────────────────────────────────────────────────────────────────────
function Footer() {
  const { user } = useAuth();
  const cols = [
    {
      title: "Product",
      links: [
        ["Agents", "/agents"],
        ["Security rules", "/security"],
        ["Live demo", "/demo"],
        ["FAQ", "/faq"],
      ],
    },
    {
      title: "Account",
      links: user
        ? [["Profile", "/profile"]]
        : [["Log in", "/login"], ["Sign up", "/signup"]],
    },
    {
      title: "Project",
      links: [
        ["GitHub", "https://github.com/shivam9473/shadowfix-ai"],
        ["README", "https://github.com/shivam9473/shadowfix-ai#readme"],
        ["Shopkart target", "https://github.com/shivam9473/shadowfix-ai/tree/main/demo-shopkart"],
      ],
    },
  ];

  return (
    <footer className="border-t border-line bg-ink-2">
      <div className="mx-auto grid max-w-7xl gap-10 px-6 py-14 md:grid-cols-[1.4fr_repeat(3,1fr)]">
        <div>
          <Logo />
          <p className="mt-4 max-w-sm text-sm leading-relaxed text-mute">
            ShadowFix is a multi-agent QA and repair desk. It reproduces a crash, names the file,
            drafts and scores a patch, and stops until an admin approves.
          </p>
        </div>
        {cols.map((col) => (
          <div key={col.title}>
            <h3 className="text-sm font-bold">{col.title}</h3>
            <ul className="mt-4 space-y-2.5 text-sm text-mute">
              {col.links.map(([label, href]) => (
                <li key={label}>
                  {href.startsWith("http") ? (
                    <a href={href} className="transition-colors hover:text-paper">
                      {label}
                    </a>
                  ) : (
                    <Link to={href} className="transition-colors hover:text-paper">
                      {label}
                    </Link>
                  )}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      <div className="border-t border-line px-6 py-5 text-center text-xs text-mute">
        © 2026 ShadowFix AI. Built by Shivam.
      </div>
    </footer>
  );
}

// ── App ───────────────────────────────────────────────────────────────────────
export default function App() {
  return (
    <div className="min-h-screen">
      <ScrollToTop />
      <AnnouncementBar />
      <Header />
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/agents" element={<AgentsPage />} />
        <Route path="/security" element={<SecurityPage />} />
        <Route path="/demo" element={<PublicDemo />} />
        <Route path="/faq" element={<FaqPage />} />
        <Route path="/login" element={<Login />} />
        <Route path="/signup" element={<Signup />} />
        <Route path="/profile" element={<Profile />} />
        <Route path="/console" element={<SuperAdminConsole />} />
        <Route path="/incident/:id" element={<IncidentRoom />} />
      </Routes>
      <Footer />
    </div>
  );
}
