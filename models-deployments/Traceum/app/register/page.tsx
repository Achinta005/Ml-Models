'use client';

import { useState, FormEvent } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAuth } from '../context/authContext';

export default function RegisterPage() {
  const { register } = useAuth();
  const router = useRouter();

  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');

    if (password !== confirm) {
      setError('Passwords do not match');
      return;
    }

    if (password.length < 8) {
      setError('Password must be at least 8 characters');
      return;
    }

    setIsLoading(true);

    try {
      await register(email.trim().toLowerCase(), password, fullName.trim());
      setSuccess(true);
    } catch (err: any) {
      setError(err.message ?? 'Registration failed. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  if (success) {
    return (
      <main className="auth-page">
        <div className="auth-card">
          <div className="success-icon">✉️</div>
          <h2>Check your email</h2>
          <p className="success-msg">
            We sent a verification link to <strong>{email}</strong>. Click it to
            activate your account.
          </p>
          <Link href="/login" className="auth-btn-link">
            Back to login
          </Link>
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
            text-align: center;
          }
          .success-icon {
            font-size: 3rem;
            margin-bottom: 1rem;
          }
          h2 {
            color: #f5f5f5;
            font-size: 1.4rem;
            margin: 0 0 0.75rem;
          }
          .success-msg {
            color: #888;
            font-size: 0.9rem;
            line-height: 1.6;
            margin-bottom: 1.5rem;
          }
          .success-msg strong {
            color: #aaa;
          }
          .auth-btn-link {
            display: inline-block;
            background: #6366f1;
            color: #fff;
            text-decoration: none;
            border-radius: 8px;
            padding: 0.7rem 1.5rem;
            font-size: 0.9rem;
            font-weight: 600;
          }
        `}</style>
      </main>
    );
  }

  return (
    <main className="auth-page">
      <div className="auth-card">
        <div className="auth-header">
          <h1>Create account</h1>
          <p>Join us today</p>
        </div>

        <form onSubmit={handleSubmit} className="auth-form" noValidate>
          {error && <div className="auth-error">{error}</div>}

          <div className="field">
            <label htmlFor="fullName">Full name</label>
            <input
              id="fullName"
              type="text"
              placeholder="Jane Smith"
              autoComplete="name"
              required
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
            />
          </div>

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
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              placeholder="Min. 8 characters"
              autoComplete="new-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>

          <div className="field">
            <label htmlFor="confirm">Confirm password</label>
            <input
              id="confirm"
              type="password"
              placeholder="••••••••"
              autoComplete="new-password"
              required
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
            />
          </div>

          <button type="submit" className="auth-btn" disabled={isLoading}>
            {isLoading ? 'Creating account…' : 'Create account'}
          </button>
        </form>

        <p className="auth-footer">
          Already have an account?{' '}
          <Link href="/login">Sign in</Link>
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