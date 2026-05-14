'use client';

import React, {
  createContext,
  useContext,
  useState,
  useEffect,
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

interface AuthState {
  user: AuthUser | null;
  accessToken: string | null;   // kept in React state only (never localStorage)
  isLoading: boolean;
  isAuthenticated: boolean;
}

interface AuthContextValue extends AuthState {
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
async function apiFetch<T = any>(
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
    credentials: 'include', // sends httpOnly refresh_token cookie automatically
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body?.message ?? `Request failed: ${res.status}`);
  }

  return res.json();
}

// ── Context ────────────────────────────────────────────────────────────────────
const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // track refresh in-flight to avoid duplicate calls
  const refreshPromiseRef = useRef<Promise<string | null> | null>(null);

  // ── Silent refresh on mount ────────────────────────────────────────────────
  const refreshAccessToken = useCallback(async (): Promise<string | null> => {
    // Deduplicate concurrent calls
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
        return newToken;
      } catch {
        setUser(null);
        setAccessToken(null);
        return null;
      } finally {
        refreshPromiseRef.current = null;
      }
    })();

    refreshPromiseRef.current = promise;
    return promise;
  }, []);

  useEffect(() => {
    refreshAccessToken().finally(() => setIsLoading(false));
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
    // refresh_token is set as httpOnly cookie by the server automatically
  }, []);

  // ── Register ───────────────────────────────────────────────────────────────
  const register = useCallback(
    async (email: string, password: string, fullName: string) => {
      await apiFetch('/auth/register', {
        method: 'POST',
        body: JSON.stringify({ email, password, fullName }),
      });
      // Don't auto-login — user needs to verify email
    },
    [],
  );

  // ── Logout ─────────────────────────────────────────────────────────────────
  const logout = useCallback(async () => {
    await apiFetch('/auth/logout', { method: 'POST' }, accessToken).catch(
      () => {},
    );
    setUser(null);
    setAccessToken(null);
    router.push('/login');
  }, [accessToken, router]);

  // ── Forgot password ────────────────────────────────────────────────────────
  const forgotPassword = useCallback(async (email: string) => {
    await apiFetch('/auth/forgot-password', {
      method: 'POST',
      body: JSON.stringify({ email }),
    });
  }, []);

  const value: AuthContextValue = {
    user,
    accessToken,
    isLoading,
    isAuthenticated: !!user && !!accessToken,
    login,
    register,
    logout,
    forgotPassword,
    refreshAccessToken,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// ── Hook ───────────────────────────────────────────────────────────────────────
export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}

// ── Axios-style fetch wrapper that auto-retries with refreshed token ───────────
// Use this in your API calls instead of raw fetch
export async function authFetch<T = any>(
  path: string,
  options: RequestInit,
  getToken: () => string | null,
  refresh: () => Promise<string | null>,
): Promise<T> {
  let token = getToken();
  try {
    return await apiFetch<T>(path, options, token);
  } catch (err: any) {
    if (err.message?.includes('401') || err.message?.includes('403')) {
      token = await refresh();
      if (!token) throw err;
      return apiFetch<T>(path, options, token);
    }
    throw err;
  }
}