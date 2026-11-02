import { createContext, useCallback, useContext, useMemo, useState } from "react";

// Front-end only accounts. Accounts live in localStorage; passwords stored as salted SHA-256 hashes.
// Swap signUp/signIn/signOut for real API calls when the backend gains auth.

const USERS_KEY = "shadowfix.users";
const SESSION_KEY = "shadowfix.session";
export const ADMIN_KEY_STORAGE = "shadowfix.adminKey";

function readUsers() {
  try {
    return JSON.parse(localStorage.getItem(USERS_KEY) || "[]");
  } catch {
    return [];
  }
}

function writeUsers(users) {
  localStorage.setItem(USERS_KEY, JSON.stringify(users));
}

async function hash(password, salt) {
  if (!globalThis.crypto?.subtle) {
    throw new Error("This browser blocks secure hashing here. Open the app on localhost or HTTPS.");
  }
  const bytes = new TextEncoder().encode(`${salt}:${password}`);
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, "0")).join("");
}

function randomSalt() {
  return Array.from(crypto.getRandomValues(new Uint8Array(12)), (b) =>
    b.toString(16).padStart(2, "0")
  ).join("");
}

function loadSession() {
  try {
    const email = localStorage.getItem(SESSION_KEY);
    if (!email) return null;
    const found = readUsers().find((u) => u.email === email);
    return found
      ? { name: found.name, email: found.email, joinedAt: found.joinedAt || "" }
      : null;
  } catch {
    return null;
  }
}

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(loadSession);
  const [adminKey, setAdminKeyState] = useState(
    () => sessionStorage.getItem(ADMIN_KEY_STORAGE) || ""
  );

  const signUp = useCallback(async ({ name, email, password }) => {
    const normalized = email.trim().toLowerCase();
    const users = readUsers();
    if (users.some((u) => u.email === normalized)) {
      throw new Error("An account with this email already exists. Log in instead.");
    }
    const salt = randomSalt();
    const joinedAt = new Date().toISOString();
    const record = {
      name: name.trim(),
      email: normalized,
      salt,
      hash: await hash(password, salt),
      joinedAt,
    };
    writeUsers([...users, record]);
    localStorage.setItem(SESSION_KEY, normalized);
    setUser({ name: record.name, email: record.email, joinedAt });
  }, []);

  const signIn = useCallback(async ({ email, password }) => {
    const normalized = email.trim().toLowerCase();
    const record = readUsers().find((u) => u.email === normalized);
    const attempt = record ? await hash(password, record.salt) : "";
    if (!record || attempt !== record.hash) {
      throw new Error("Email or password is incorrect.");
    }
    localStorage.setItem(SESSION_KEY, normalized);
    setUser({ name: record.name, email: record.email, joinedAt: record.joinedAt || "" });
  }, []);

  const signOut = useCallback(() => {
    localStorage.removeItem(SESSION_KEY);
    sessionStorage.removeItem(ADMIN_KEY_STORAGE);
    setAdminKeyState("");
    setUser(null);
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

  const value = useMemo(
    () => ({
      user,
      signUp,
      signIn,
      signOut,
      adminKey,
      saveAdminKey,
      hasAdminKey: !!adminKey,
    }),
    [user, signUp, signIn, signOut, adminKey, saveAdminKey]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
