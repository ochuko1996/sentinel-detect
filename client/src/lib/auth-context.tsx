"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { authStorage, type StoredIdentity } from "./api";

interface AuthContextValue {
  identity: StoredIdentity | null;
  /** True once the client has checked localStorage for a stored session —
   * gates rendering so server-rendered and first-client-render markup match
   * (there is no session info available during SSR). */
  ready: boolean;
  setIdentity: (identity: StoredIdentity | null) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [identity, setIdentityState] = useState<StoredIdentity | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    setIdentityState(authStorage.getIdentity());
    setReady(true);
  }, []);

  function logout() {
    authStorage.clear();
    setIdentityState(null);
  }

  return (
    <AuthContext.Provider
      value={{ identity, ready, setIdentity: setIdentityState, logout }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
