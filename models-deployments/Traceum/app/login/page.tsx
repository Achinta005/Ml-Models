'use client';

import { useState, FormEvent } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAuth } from '../context/authContext';

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      await login(email.trim().toLowerCase(), password);
      router.push('/dashboard');
    } catch (err: any) {
      setError(err.message ?? 'Login failed. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <main className="auth-page">
      <div className="auth-card">
        <div className="auth-header">
          <h1>Welcome back</h1>
          <p>Sign in to your account</p>
        </div>

        <form onSubmit={handleSubmit} className="auth-form" noValidate>
          {error && <div className="auth-error">{error}</div>}

          <div className="field">
            <label htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              placeholder="you@example.com"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>

          <div className="field">
            <label htmlFor="password">
              Password
              <Link href="/forgot-password" className="forgot-link">
                Forgot password?
              </Link>
            </label>
            <input
              id="password"
              type="password"
              placeholder="••••••••"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>

          <button type="submit" className="auth-btn" disabled={isLoading}>
            {isLoading ? 'Signing in…' : 'Sign in'}
          </button>
        </form>

        <p className="auth-footer">
          Don&apos;t have an account?{' '}
          <Link href="/register">Create one</Link>
        </p>
      </div>

      <style jsx>{`
        .auth-page {
          min-height: 100vh;
          display: flex;
          align-items: center;
          justify-content: center;
          background: #0f0f0f;
          padding: 1.5rem;
        }

        .auth-card {
          width: 100%;
          max-width: 400px;
          background: #1a1a1a;
          border: 1px solid #2a2a2a;
          border-radius: 12px;
          padding: 2.5rem 2rem;
        }

        .auth-header {
          margin-bottom: 2rem;
        }

        .auth-header h1 {
          font-size: 1.6rem;
          font-weight: 700;
          color: #f5f5f5;
          margin: 0 0 0.25rem;
        }

        .auth-header p {
          color: #777;
          font-size: 0.9rem;
          margin: 0;
        }

        .auth-form {
          display: flex;
          flex-direction: column;
          gap: 1.2rem;
        }

        .auth-error {
          background: #2d1a1a;
          border: 1px solid #5c2626;
          color: #f87171;
          padding: 0.7rem 0.9rem;
          border-radius: 8px;
          font-size: 0.875rem;
        }

        .field {
          display: flex;
          flex-direction: column;
          gap: 0.4rem;
        }

        .field label {
          font-size: 0.85rem;
          font-weight: 500;
          color: #aaa;
          display: flex;
          justify-content: space-between;
          align-items: center;
        }

        .forgot-link {
          font-size: 0.8rem;
          color: #6366f1;
          text-decoration: none;
        }

        .forgot-link:hover {
          text-decoration: underline;
        }

        .field input {
          background: #111;
          border: 1px solid #2e2e2e;
          border-radius: 8px;
          color: #f5f5f5;
          font-size: 0.95rem;
          padding: 0.65rem 0.9rem;
          outline: none;
          transition: border-color 0.15s;
        }

        .field input::placeholder {
          color: #444;
        }

        .field input:focus {
          border-color: #6366f1;
        }

        .auth-btn {
          margin-top: 0.5rem;
          background: #6366f1;
          color: #fff;
          border: none;
          border-radius: 8px;
          padding: 0.75rem;
          font-size: 0.95rem;
          font-weight: 600;
          cursor: pointer;
          transition: background 0.15s, opacity 0.15s;
        }

        .auth-btn:hover:not(:disabled) {
          background: #4f46e5;
        }

        .auth-btn:disabled {
          opacity: 0.55;
          cursor: not-allowed;
        }

        .auth-footer {
          margin-top: 1.5rem;
          text-align: center;
          color: #666;
          font-size: 0.875rem;
        }

        .auth-footer a {
          color: #6366f1;
          text-decoration: none;
          font-weight: 500;
        }

        .auth-footer a:hover {
          text-decoration: underline;
        }
      `}</style>
    </main>
  );
}