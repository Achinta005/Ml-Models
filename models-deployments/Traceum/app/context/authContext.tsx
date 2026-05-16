'use client';

import React, {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  useRef,
  ReactNode,
} from 'react';
import { useRouter } from 'next/navigation';

// ── Types ──────────────────────────────────────────────────────────────────────
export interface AuthUser {
  id: string;
  email: string;
  fullName?: string;
  roles?: string[];
}

interface AuthSession {
  access_token: string;
  expires_at?: number;
}

interface AuthContextValue {
  user: AuthUser | null;
  accessToken: string | null;
  isAuthenticated: boolean;
  isAuthLoading: boolean;
  setAccessToken: (token: string | null) => void;
  setIsAuthenticated: (val: boolean) => void;
  setUser: (user: AuthUser | null) => void;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, fullName: string) => Promise<void>;
  logout: () => Promise<void>;
  forgotPassword: (email: string) => Promise<void>;
  refreshAccessToken: () => Promise<string | null>;
}

// ── Config ─────────────────────────────────────────────────────────────────────
const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:3001/api';
const PROJECT = 'traceum';

// ── Helpers ────────────────────────────────────────────────────────────────────
async function apiFetch<T = unknown>(
  path: string,
  options: RequestInit = {},
  accessToken?: string | null,
): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };

  if (accessToken) headers['Authorization'] = `Bearer ${accessToken}`;

  const res = await fetch(`${API_BASE}/${PROJECT}${path}`, {
    ...options,
    headers,
    credentials: 'include',
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({})) as { message?: string };
    throw new Error(body?.message ?? `Request failed: ${res.status}`);
  }

  return res.json() as Promise<T>;
}

// ── Context ────────────────────────────────────────────────────────────────────
const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isAuthLoading, setIsAuthLoading] = useState(true);

  const refreshPromiseRef = useRef<Promise<string | null> | null>(null);

  // ── Silent refresh ─────────────────────────────────────────────────────────
  const refreshAccessToken = useCallback(async (): Promise<string | null> => {
    if (refreshPromiseRef.current) return refreshPromiseRef.current;

    const promise = (async () => {
      try {
        const data = await apiFetch<{
          success: boolean;
          data: { user: AuthUser; session: AuthSession };
        }>('/auth/refresh', { method: 'POST' });

        const newToken = data.data.session.access_token;
        setUser(data.data.user);
        setAccessToken(newToken);
        setIsAuthenticated(true);
        return newToken;
      } catch {
        setUser(null);
        setAccessToken(null);
        setIsAuthenticated(false);
        return null;
      } finally {
        refreshPromiseRef.current = null;
      }
    })();

    refreshPromiseRef.current = promise;
    return promise;
  }, []);

  // ── Restore session on mount ───────────────────────────────────────────────
  useEffect(() => {
    const restoreSession = async () => {
      try {
        const token = await refreshAccessToken();
        if (!token) {
          setIsAuthenticated(false);
          setUser(null);
          setAccessToken(null);
        }
      } finally {
        setIsAuthLoading(false);
      }
    };

    restoreSession();
  }, [refreshAccessToken]);

  // ── Login ──────────────────────────────────────────────────────────────────
  const login = useCallback(async (email: string, password: string) => {
    const data = await apiFetch<{
      success: boolean;
      data: { user: AuthUser; session: AuthSession };
    }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });

    setUser(data.data.user);
    setAccessToken(data.data.session.access_token);
    setIsAuthenticated(true);
  }, []);

  // ── Register ───────────────────────────────────────────────────────────────
  const register = useCallback(
    async (email: string, password: string, fullName: string) => {
      await apiFetch('/auth/register', {
        method: 'POST',
        body: JSON.stringify({ email, password, fullName }),
      });
    },
    [],
  );

  // ── Logout ─────────────────────────────────────────────────────────────────
  const logout = useCallback(async () => {
    await apiFetch('/auth/logout', { method: 'POST' }, accessToken).catch(() => {});
    setUser(null);
    setAccessToken(null);
    setIsAuthenticated(false);
    router.push('/login');
  }, [accessToken, router]);

  // ── Forgot password ────────────────────────────────────────────────────────
  const forgotPassword = useCallback(async (email: string) => {
    await apiFetch('/auth/forgot-password', {
      method: 'POST',
      body: JSON.stringify({ email }),
    });
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        accessToken,
        isAuthenticated,
        isAuthLoading,
        setUser,
        setAccessToken,
        setIsAuthenticated,
        login,
        register,
        logout,
        forgotPassword,
        refreshAccessToken,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

// ── Hook ───────────────────────────────────────────────────────────────────────
export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}

// ── authFetch — auto-retries with refreshed token ─────────────────────────────
export async function authFetch<T = unknown>(
  path: string,
  options: RequestInit,
  getToken: () => string | null,
  refresh: () => Promise<string | null>,
): Promise<T> {
  let token = getToken();
  try {
    return await apiFetch<T>(path, options, token);
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : '';
    if (message.includes('401') || message.includes('403')) {
      token = await refresh();
      if (!token) throw err;
      return apiFetch<T>(path, options, token);
    }
    throw err;
  }
}