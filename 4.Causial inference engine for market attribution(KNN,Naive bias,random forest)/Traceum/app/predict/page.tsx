'use client';

import React, { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '../context/authContext';

// ── Types ──────────────────────────────────────────────────────────────────────

interface UserRole {
  id: number;
  userId: string;
  projectName: string;
  projectId: number;
  roleId: number;
  assignedBy: string | null;
  assignedAt: string;
  role: {
    id: number;
    name: string;
    slug: string;
    description: string;
    isActive: boolean;
    isSystem: boolean;
    createdAt: string;
    updatedAt: string;
  };
}

interface UserProfile {
  id: string;
  projectName: string;
  projectId: number;
  email: string;
  fullName: string;
  username: string;
  avatarUrl: string | null;
  phoneNumber: string | null;
  bio: string | null;
  isActive: boolean;
  isEmailVerified: boolean;
  isMfaEnabled: boolean;
  lastLoginAt: string;
  lastLoginIp: string;
  metadata: Record<string, any>;
  createdAt: string;
  updatedAt: string;
  userRoles: UserRole[];
}

interface TraceumDataset {
  id: string;
  f0: number; f1: number; f2: number; f3: number;
  f4: number; f5: number; f6: number; f7: number;
  f8: number; f9: number; f10: number; f11: number;
  treatment: number;
  conversion: number;
  exposure: number;
  visit: number;
  session_id: string;
  user_id: string;
  avg_item_value: number;
  is_high_intent: boolean;
  created_at: string;
}

interface UpliftResult {
  uplift_t: number;
  uplift_s: number;
  avg_uplift: number;
  send_ad?: boolean;
}

interface UserRow {
  dataset: TraceumDataset;
  profile: UserProfile | null;
}

interface PredictionResult {
  user: TraceumDataset;
  uplift: UpliftResult | null;
}

// ── Constants ──────────────────────────────────────────────────────────────────

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:3001/api';
const PROJECT = 'traceum';

// ── Page Component ─────────────────────────────────────────────────────────────

export default function PredictPage() {
  const router = useRouter();
  const { accessToken, refreshAccessToken } = useAuth();

  const [users, setUsers] = useState<UserRow[]>([]);
  const [loadingUsers, setLoadingUsers] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);

  // per-user prediction state
  const [predictions, setPredictions] = useState<Record<string, UpliftResult | null>>({});
  const [predicting, setPredicting] = useState<Record<string, boolean>>({});
  const [predError, setPredError] = useState<Record<string, string | null>>({});

  // expanded row state
  const [expandedRow, setExpandedRow] = useState<string | null>(null);

  // ── apiFetch with auto-refresh ───────────────────────────────────────────────

  const apiFetch = useCallback(
    async <T = any>(path: string, options: RequestInit = {}): Promise<T> => {
      const doFetch = async (token: string | null) => {
        const headers: Record<string, string> = {
          'Content-Type': 'application/json',
          ...(options.headers as Record<string, string>),
        };
        if (token) headers['Authorization'] = `Bearer ${token}`;

        const res = await fetch(`${API_BASE}/${PROJECT}${path}`, {
          ...options,
          headers,
          credentials: 'include',
        });

        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          throw new Error(body?.message ?? `Request failed: ${res.status}`);
        }
        return res.json() as Promise<T>;
      };

      try {
        return await doFetch(accessToken);
      } catch (err: any) {
        if (err.message?.includes('401') || err.message?.includes('403')) {
          const newToken = await refreshAccessToken();
          if (!newToken) throw err;
          return doFetch(newToken);
        }
        throw err;
      }
    },
    [accessToken, refreshAccessToken],
  );

  // ── Fetch all users ──────────────────────────────────────────────────────────

  useEffect(() => {
    const load = async () => {
      try {
        setLoadingUsers(true);
        setFetchError(null);
        const data = await apiFetch<UserRow[]>('/users');
        setUsers(data);
      } catch (err: any) {
        setFetchError(err.message ?? 'Failed to fetch users');
      } finally {
        setLoadingUsers(false);
      }
    };
    load();
  }, [apiFetch]);

  // ── Predict for a single user ────────────────────────────────────────────────

  const handlePredict = useCallback(
    async (userId: string) => {
      setPredicting((p) => ({ ...p, [userId]: true }));
      setPredError((p) => ({ ...p, [userId]: null }));
      try {
        const data = await apiFetch<PredictionResult>(`/${userId}`);
        setPredictions((p) => ({ ...p, [userId]: data.uplift }));
      } catch (err: any) {
        setPredError((p) => ({ ...p, [userId]: err.message ?? 'Prediction failed' }));
      } finally {
        setPredicting((p) => ({ ...p, [userId]: false }));
      }
    },
    [apiFetch],
  );

  // ── Helpers ──────────────────────────────────────────────────────────────────

  const upliftColor = (val: number) => {
    if (val > 0.05) return '#22c55e';
    if (val < -0.05) return '#ef4444';
    return '#f59e0b';
  };

  const formatDate = (iso: string) =>
    new Date(iso).toLocaleDateString('en-IN', {
      day: '2-digit', month: 'short', year: 'numeric',
    });

  // ── Render ───────────────────────────────────────────────────────────────────

  return (
    <div style={styles.page}>
      <button
        onClick={() => router.push('/dashboard')}
        style={styles.backBtn}
      >
        ← Back
      </button>

      {/* Header */}
      <div style={styles.header}>
        <div>
          <p style={styles.headerEyebrow}>TRACEUM DASHBOARD</p>
          <h1 style={styles.headerTitle}>Uplift Predictions</h1>
        </div>
        <div style={styles.headerMeta}>
          {!loadingUsers && (
            <span style={styles.countBadge}>{users.length} users</span>
          )}
        </div>
      </div>

      {/* Error */}
      {fetchError && (
        <div style={styles.errorBox}>
          <span style={styles.errorIcon}>⚠</span> {fetchError}
        </div>
      )}

      {/* Loading */}
      {loadingUsers && (
        <div style={styles.loadingWrap}>
          <div style={styles.spinner} />
          <p style={styles.loadingText}>Loading users…</p>
        </div>
      )}

      {/* Table */}
      {!loadingUsers && !fetchError && (
        <div style={styles.tableWrap}>
          <table style={styles.table}>
            <thead>
              <tr>
                {['User', 'Email', 'Role', 'Session', 'Intent', 'Avg Item Value', 'Joined', 'Predict'].map((h) => (
                  <th key={h} style={styles.th}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {users.map((row) => {
                const uid = row.dataset.user_id;
                const p = predictions[uid];
                const isExpanded = expandedRow === uid;

                return (
                  <React.Fragment key={row.dataset.id}>
                    <tr
                      style={{
                        ...styles.tr,
                        ...(isExpanded ? styles.trExpanded : {}),
                      }}
                      onClick={() => setExpandedRow(isExpanded ? null : uid)}
                    >
                      {/* User */}
                      <td style={styles.td}>
                        <div style={styles.userCell}>
                          <div style={styles.avatar}>
                            {row.profile?.fullName?.[0]?.toUpperCase() ?? '?'}
                          </div>
                          <div>
                            <div style={styles.userName}>
                              {row.profile?.fullName ?? '—'}
                            </div>
                            <div style={styles.userId}>{uid.slice(0, 8)}…</div>
                          </div>
                        </div>
                      </td>

                      {/* Email */}
                      <td style={styles.td}>
                        <span style={styles.mono}>{row.profile?.email ?? '—'}</span>
                      </td>

                      {/* Role */}
                      <td style={styles.td}>
                        {row.profile?.userRoles?.[0]?.role.name ? (
                          <span style={styles.roleBadge}>
                            {row.profile.userRoles[0].role.name}
                          </span>
                        ) : '—'}
                      </td>

                      {/* Session */}
                      <td style={styles.td}>
                        <span style={styles.mono}>{row.dataset.session_id}</span>
                      </td>

                      {/* Intent */}
                      <td style={styles.td}>
                        <span style={{
                          ...styles.intentBadge,
                          background: row.dataset.is_high_intent ? '#14532d' : '#1c1917',
                          color: row.dataset.is_high_intent ? '#4ade80' : '#78716c',
                          border: `1px solid ${row.dataset.is_high_intent ? '#166534' : '#292524'}`,
                        }}>
                          {row.dataset.is_high_intent ? 'High' : 'Low'}
                        </span>
                      </td>

                      {/* Avg item value */}
                      <td style={{ ...styles.td, ...styles.mono }}>
                        ₹{row.dataset.avg_item_value}
                      </td>

                      {/* Joined */}
                      <td style={{ ...styles.td, ...styles.dimText }}>
                        {row.profile?.createdAt ? formatDate(row.profile.createdAt) : '—'}
                      </td>

                      {/* Predict button */}
                      <td style={styles.td} onClick={(e) => e.stopPropagation()}>
                        <button
                          style={{
                            ...styles.predictBtn,
                            ...(predicting[uid] ? styles.predictBtnLoading : {}),
                            ...(p ? styles.predictBtnDone : {}),
                          }}
                          onClick={() => handlePredict(uid)}
                          disabled={predicting[uid]}
                        >
                          {predicting[uid]
                            ? 'Running…'
                            : p
                            ? '↻ Re-run'
                            : '▶ Predict'}
                        </button>
                      </td>
                    </tr>

                    {/* Expanded: prediction result */}
                    {isExpanded && (
                      <tr>
                        <td colSpan={8} style={styles.expandedCell}>
                          <div style={styles.expandedContent}>

                            {/* ── Always shown: dataset values from /users ── */}
                            <div style={styles.expandSection}>
                              <p style={styles.expandLabel}>FEATURE VECTOR</p>
                              <div style={styles.featureGrid}>
                                {Array.from({ length: 12 }, (_, i) => {
                                  const key = `f${i}` as keyof TraceumDataset;
                                  const val = row.dataset[key] as number;
                                  return (
                                    <div key={i} style={styles.featureCell}>
                                      <span style={styles.featureKey}>f{i}</span>
                                      <span style={styles.featureVal}>{val?.toFixed(4)}</span>
                                    </div>
                                  );
                                })}
                              </div>

                              <p style={{ ...styles.expandLabel, marginTop: '16px' }}>TREATMENT / OUTCOME</p>
                              <div style={styles.featureGrid}>
                                {[
                                  ['treatment', row.dataset.treatment],
                                  ['conversion', row.dataset.conversion],
                                  ['exposure', row.dataset.exposure],
                                  ['visit', row.dataset.visit],
                                ].map(([k, v]) => (
                                  <div key={k} style={styles.featureCell}>
                                    <span style={styles.featureKey}>{k}</span>
                                    <span style={styles.featureVal}>{v}</span>
                                  </div>
                                ))}
                              </div>
                            </div>

                            {/* ── Only shown after predict click: uplift from /:userId ── */}
                            <div style={styles.expandSection}>
                              <p style={styles.expandLabel}>UPLIFT PREDICTION</p>

                              {!predictions[uid] && !predicting[uid] && !predError[uid] && (
                                <p style={styles.dimText}>Hit ▶ Predict to score this user.</p>
                              )}

                              {predicting[uid] && (
                                <p style={styles.dimText}>Scoring…</p>
                              )}

                              {predError[uid] && !predicting[uid] && (
                                <p style={styles.predErrorText}>⚠ {predError[uid]}</p>
                              )}

                              {predictions[uid] && !predicting[uid] && (
                                <div style={styles.upliftGrid}>
                                  {[
                                    { label: 'T-Learner',  value: predictions[uid]!.uplift_t  },
                                    { label: 'S-Learner',  value: predictions[uid]!.uplift_s  },
                                    { label: 'Avg Uplift', value: predictions[uid]!.avg_uplift },
                                  ].map(({ label, value }) => (
                                    <div key={label} style={styles.upliftCard}>
                                      <span style={styles.upliftLabel}>{label}</span>
                                      <span style={{ ...styles.upliftValue, color: upliftColor(value) }}>
                                        {value >= 0 ? '+' : ''}{value.toFixed(6)}
                                      </span>
                                    </div>
                                  ))}
                                  {predictions[uid]!.send_ad !== undefined && (
                                    <div style={styles.upliftCard}>
                                      <span style={styles.upliftLabel}>Send Ad?</span>
                                      <span style={{
                                        ...styles.upliftValue,
                                        color: predictions[uid]!.send_ad ? '#22c55e' : '#ef4444',
                                      }}>
                                        {predictions[uid]!.send_ad ? '✓ Yes' : '✗ No'}
                                      </span>
                                    </div>
                                  )}
                                </div>
                              )}
                            </div>

                            {/* ── Always shown: profile details from /users ── */}
                            {row.profile && (
                              <div style={styles.expandSection}>
                                <p style={styles.expandLabel}>PROFILE DETAILS</p>
                                <div style={styles.profileGrid}>
                                  {[
                                    ['Username',       row.profile.username],
                                    ['Last Login',     formatDate(row.profile.lastLoginAt)],
                                    ['Last IP',        row.profile.lastLoginIp],
                                    ['Email Verified', row.profile.isEmailVerified ? 'Yes' : 'No'],
                                    ['MFA',            row.profile.isMfaEnabled   ? 'Enabled' : 'Disabled'],
                                    ['Active',         row.profile.isActive       ? 'Yes' : 'No'],
                                  ].map(([k, v]) => (
                                    <div key={k} style={styles.profileRow}>
                                      <span style={styles.profileKey}>{k}</span>
                                      <span style={styles.profileVal}>{v}</span>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })}
            </tbody>
          </table>

          {users.length === 0 && (
            <div style={styles.emptyState}>No users found.</div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Styles ─────────────────────────────────────────────────────────────────────

const styles: Record<string, React.CSSProperties> = {
  page: {
    minHeight: '100vh',
    background: '#0a0a0a',
    color: '#e2e8f0',
    fontFamily: "'IBM Plex Mono', 'Fira Code', monospace",
    padding: '40px 32px',
  },
  header: {
    display: 'flex',
    alignItems: 'flex-end',
    justifyContent: 'space-between',
    marginBottom: '32px',
    borderBottom: '1px solid #1e1e1e',
    paddingBottom: '20px',
  },
  headerEyebrow: {
    fontSize: '11px',
    letterSpacing: '0.15em',
    color: '#4a5568',
    margin: '0 0 6px',
  },
  headerTitle: {
    fontSize: '28px',
    fontWeight: 700,
    margin: 0,
    color: '#f8fafc',
    letterSpacing: '-0.02em',
  },
  headerMeta: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
  },
  countBadge: {
    background: '#1a1a1a',
    border: '1px solid #2d2d2d',
    borderRadius: '6px',
    padding: '4px 12px',
    fontSize: '12px',
    color: '#94a3b8',
  },
  errorBox: {
    background: '#1c0a0a',
    border: '1px solid #7f1d1d',
    borderRadius: '8px',
    padding: '12px 16px',
    color: '#fca5a5',
    fontSize: '13px',
    marginBottom: '24px',
  },
  errorIcon: {
    marginRight: '8px',
  },
  loadingWrap: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: '16px',
    marginTop: '80px',
  },
  spinner: {
    width: '32px',
    height: '32px',
    border: '2px solid #1e1e1e',
    borderTop: '2px solid #3b82f6',
    borderRadius: '50%',
    animation: 'spin 0.8s linear infinite',
  },
  loadingText: {
    color: '#4a5568',
    fontSize: '13px',
    margin: 0,
  },
  tableWrap: {
    overflowX: 'auto',
    borderRadius: '10px',
    border: '1px solid #1e1e1e',
  },
  table: {
    width: '100%',
    borderCollapse: 'collapse',
    fontSize: '13px',
  },
  th: {
    padding: '12px 16px',
    textAlign: 'left',
    fontSize: '10px',
    letterSpacing: '0.12em',
    color: '#4a5568',
    background: '#0f0f0f',
    borderBottom: '1px solid #1e1e1e',
    fontWeight: 600,
    textTransform: 'uppercase',
    whiteSpace: 'nowrap',
  },
  tr: {
    borderBottom: '1px solid #141414',
    cursor: 'pointer',
    transition: 'background 0.15s',
  },
  trExpanded: {
    background: '#111111',
  },
  td: {
    padding: '14px 16px',
    verticalAlign: 'middle',
    color: '#cbd5e1',
  },
  userCell: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
  },
  avatar: {
    width: '32px',
    height: '32px',
    borderRadius: '8px',
    background: '#1a2744',
    border: '1px solid #1e3a5f',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: '13px',
    fontWeight: 700,
    color: '#60a5fa',
    flexShrink: 0,
  },
  userName: {
    fontWeight: 600,
    color: '#f1f5f9',
    fontSize: '13px',
  },
  userId: {
    fontSize: '11px',
    color: '#4a5568',
    marginTop: '2px',
  },
  mono: {
    fontFamily: 'inherit',
    fontSize: '12px',
    color: '#94a3b8',
  },
  roleBadge: {
    background: '#1a1a2e',
    border: '1px solid #2d2d5e',
    borderRadius: '4px',
    padding: '2px 8px',
    fontSize: '11px',
    color: '#818cf8',
  },
  intentBadge: {
    borderRadius: '4px',
    padding: '2px 8px',
    fontSize: '11px',
    fontWeight: 600,
  },
  dimText: {
    color: '#4a5568',
    fontSize: '12px',
  },
  predictBtn: {
    background: '#0f172a',
    border: '1px solid #1e3a5f',
    borderRadius: '6px',
    color: '#60a5fa',
    fontSize: '12px',
    fontFamily: 'inherit',
    padding: '6px 14px',
    cursor: 'pointer',
    whiteSpace: 'nowrap',
    transition: 'all 0.15s',
  },
  predictBtnLoading: {
    color: '#4a5568',
    borderColor: '#1e1e1e',
    cursor: 'not-allowed',
  },
  predictBtnDone: {
    borderColor: '#166534',
    color: '#4ade80',
    background: '#052e16',
  },
  expandedCell: {
    padding: 0,
    background: '#080808',
    borderBottom: '1px solid #1e1e1e',
  },
  expandedContent: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
    gap: '0',
    padding: '20px 24px',
  },
  expandSection: {
    padding: '0 20px 0 0',
    borderRight: '1px solid #141414',
    marginRight: '20px',
  },
  expandLabel: {
    fontSize: '10px',
    letterSpacing: '0.15em',
    color: '#4a5568',
    marginBottom: '12px',
    margin: '0 0 12px',
  },
  featureGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(4, 1fr)',
    gap: '6px',
  },
  featureCell: {
    background: '#0f0f0f',
    border: '1px solid #1a1a1a',
    borderRadius: '4px',
    padding: '6px 8px',
    display: 'flex',
    flexDirection: 'column',
    gap: '2px',
  },
  featureKey: {
    fontSize: '10px',
    color: '#4a5568',
  },
  featureVal: {
    fontSize: '11px',
    color: '#94a3b8',
    fontFamily: 'inherit',
  },
  upliftGrid: {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
  },
  upliftCard: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    background: '#0f0f0f',
    border: '1px solid #1a1a1a',
    borderRadius: '6px',
    padding: '8px 12px',
  },
  upliftLabel: {
    fontSize: '11px',
    color: '#64748b',
  },
  upliftValue: {
    fontSize: '13px',
    fontWeight: 700,
    fontFamily: 'inherit',
  },
  predErrorText: {
    color: '#fca5a5',
    fontSize: '12px',
    margin: 0,
  },
  profileGrid: {
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
  },
  profileRow: {
    display: 'flex',
    justifyContent: 'space-between',
    fontSize: '12px',
    padding: '4px 0',
    borderBottom: '1px solid #111',
  },
  profileKey: {
    color: '#4a5568',
  },
  profileVal: {
    color: '#94a3b8',
  },
  emptyState: {
    textAlign: 'center',
    padding: '60px',
    color: '#4a5568',
    fontSize: '13px',
  },
  backBtn: {
    background: 'transparent',
    border: '1px solid #1e1e1e',
    borderRadius: '6px',
    color: '#4a5568',
    fontSize: '12px',
    fontFamily: 'inherit',
    padding: '6px 14px',
    cursor: 'pointer',
    marginBottom: '24px',
    letterSpacing: '0.05em',
    transition: 'color 0.15s, border-color 0.15s',
  },
};