'use client';

import { useState, useEffect } from 'react';
import { getFeatureVector, getSessionId } from '../lib/tracker';

const F_LABELS = [
  'f0_cart_items', 'f1_cart_value', 'f2_categories_seen',
  'f3_product_views', 'f4_search_count', 'f5_session_duration',
  'f6_scroll_depth', 'f7_wishlist_adds', 'f8_click_count',
  'f9_checkout_starts', 'f10_device_type', 'f11_referral_encoded',
] as const;

export function FeatureDebug() {
  const [open, setOpen] = useState(false);
  const [fv, setFv] = useState(getFeatureVector());

  useEffect(() => {
    const interval = setInterval(() => setFv(getFeatureVector()), 800);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="fixed bottom-4 right-4 z-50 font-mono text-xs">
      <button
        data-no-track
        onClick={() => setOpen(o => !o)}
        className="bg-emerald-400/10 border border-emerald-400/30 text-emerald-400 px-3 py-1.5 rounded-lg hover:bg-emerald-400/20 transition-colors"
      >
        {open ? '✕ features' : '⬡ features'}
      </button>

      {open && (
        <div className="absolute bottom-10 right-0 w-64 bg-[#111] border border-white/10 rounded-xl p-4 shadow-2xl">
          <p className="text-white/30 mb-3 truncate">sid: {getSessionId()}</p>
          <div className="space-y-1.5">
            {F_LABELS.map(k => {
              const key = String(k);
              const short = key.split('_')[0]; // f0, f1 …
              const label = key.slice(short.length + 1).replace(/_/g, ' ');
              const val = fv[k as keyof typeof fv];
              return (
                <div key={key} className="flex justify-between items-center">
                  <span className="text-white/30">
                    <span className="text-emerald-400">{short}</span> {label}
                  </span>
                  <span className="text-white/70 tabular-nums">{typeof val === 'number' ? val : String(val)}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}