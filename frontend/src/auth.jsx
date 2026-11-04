import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

const TOKEN_KEY = "shadowfix.token";
const USER_KEY = "shadowfix.user";
export const ADMIN_KEY_STORAGE = "shadowfix.adminKey";

function getStoredToken() {
  return localStorage.getItem(TOKEN_KEY) || "";
}

function getStoredUser() {
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setToken] = useState(getStoredToken);
  const [user, setUser] = useState(getStoredUser);
  const [adminKey, setAdminKeyState] = useState(
    () => sessionStorage.getItem(ADMIN_KEY_STORAGE) || ""
  );

  // Sync token to user session validation
  useEffect(() => {
    if (!token) return;
    fetch("/api/auth/me", {
      headers: { "X-Session-Token": token },
    })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data?.user) {
          setUser(data.user);
          localStorage.setItem(USER_KEY, JSON.stringify(data.user));
          if (data.user.role === "super_admin") {
            setAdminKeyState("Shadowfix@4321");
            sessionStorage.setItem(ADMIN_KEY_STORAGE, "Shadowfix@4321");
          }
        }
      })
      .catch(() => {});
  }, [token]);

  const signUp = useCallback(async ({ name, email, password, organizationName }) => {
    const res = await fetch("/api/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: name.trim(),
        email: email.trim().toLowerCase(),
        password,
        organization_name: organizationName || undefined,
      }),
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "Registration failed.");
    }
    const authUser = data.user;
    setToken(authUser.token);
    setUser(authUser);
    localStorage.setItem(TOKEN_KEY, authUser.token);
    localStorage.setItem(USER_KEY, JSON.stringify(authUser));
    return authUser;
  }, []);

  const signIn = useCallback(async ({ email, password }) => {
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: email.trim().toLowerCase(),
        password,
      }),
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "Authentication failed.");
    }
    const authUser = data.user;
    setToken(authUser.token);
    setUser(authUser);
    localStorage.setItem(TOKEN_KEY, authUser.token);
    localStorage.setItem(USER_KEY, JSON.stringify(authUser));
    if (authUser.role === "super_admin") {
      setAdminKeyState("Shadowfix@4321");
      sessionStorage.setItem(ADMIN_KEY_STORAGE, "Shadowfix@4321");
    }
    return authUser;
  }, []);

  const signOut = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    sessionStorage.removeItem(ADMIN_KEY_STORAGE);
    setToken("");
    setUser(null);
    setAdminKeyState("");
  }, []);

  const saveAdminKey = useCallback((key) => {
    if (key) {
      sessionStorage.setItem(ADMIN_KEY_STORAGE, key);
      setAdminKeyState(key);
    } else {
      sessionStorage.removeItem(ADMIN_KEY_STORAGE);
      setAdminKeyState("");
    }
  }, []);

  const refreshUser = useCallback(async () => {
    if (!token) return;
    try {
      const res = await fetch("/api/auth/me", {
        headers: { "X-Session-Token": token },
      });
      if (res.ok) {
        const data = await res.json();
        setUser(data.user);
        localStorage.setItem(USER_KEY, JSON.stringify(data.user));
      }
    } catch {}
  }, [token]);

  const isSuperAdmin = user?.role === "super_admin" || !!adminKey;
  const isUserAdmin = user?.role === "user_admin";

  const value = useMemo(
    () => ({
      user,
      token,
      signUp,
      signIn,
      signOut,
      refreshUser,
      adminKey,
      saveAdminKey,
      hasAdminKey: !!adminKey || isSuperAdmin,
      isSuperAdmin,
      isUserAdmin,
    }),
    [user, token, signUp, signIn, signOut, refreshUser, adminKey, saveAdminKey, isSuperAdmin, isUserAdmin]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
