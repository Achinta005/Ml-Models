'use client';

function generateSessionId() {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

function detectDeviceType(): number {
  if (typeof navigator === 'undefined') return 0;
  const ua = navigator.userAgent;
  if (/tablet|ipad/i.test(ua)) return 2;
  if (/mobile|android|iphone/i.test(ua)) return 1;
  return 0;
}

function encodeReferral(ref: string): number {
  if (!ref || ref === 'direct') return 0;
  if (/organic|google|bing/i.test(ref)) return 1;
  if (/paid|cpc|ad/i.test(ref)) return 2;
  if (/social|twitter|facebook|instagram/i.test(ref)) return 3;
  if (/email|newsletter/i.test(ref)) return 4;
  return 0;
}

const defaultFeatures = () => ({
  f0_cart_items: 0,
  f1_cart_value: 0,
  f2_categories_seen: 0,
  f3_product_views: 0,
  f4_search_count: 0,
  f5_session_duration: 0,
  f6_scroll_depth: 0,
  f7_wishlist_adds: 0,
  f8_click_count: 0,
  f9_checkout_starts: 0,
  f10_device_type: detectDeviceType(),
  f11_referral_encoded: encodeReferral(
    typeof document !== 'undefined' ? document.referrer : ''
  ),
});

interface TrackerState {
  sessionId: string;
  pageEnterTime: number;
  scrollSamples: number[];
  features: Record<string, number>;
  _categoriesSeen: Set<string>;
  _pageViewFired: boolean;
  _checkoutCompleted: boolean;
}

let _state: TrackerState | null = null;

function getState(): TrackerState {
  if (!_state) {
    _state = {
      sessionId: generateSessionId(),
      pageEnterTime: Date.now(),
      scrollSamples: [],
      features: defaultFeatures(),
      _categoriesSeen: new Set(),
      _pageViewFired: false,
      _checkoutCompleted: false,
    };
  }
  return _state;
}

// ── Normalization ─────────────────────────────────────────────────────────────
// Training data was generated with np.random.normal(0, 10) for all features.
// Real tracker data has different scales — we normalize to match (mean=0, std=10).

const REAL_STATS: Record<string, { mean: number; std: number }> = {
  f0:  { mean: 2,    std: 3    },  // cart_items       (0–20 typical)
  f1:  { mean: 500,  std: 600  },  // cart_value $     (0–3000 typical)
  f2:  { mean: 2,    std: 2    },  // categories_seen  (0–10 typical)
  f3:  { mean: 5,    std: 5    },  // product_views    (0–30 typical)
  f4:  { mean: 1,    std: 2    },  // search_count     (0–10 typical)
  f5:  { mean: 120,  std: 180  },  // session_duration (seconds)
  f6:  { mean: 40,   std: 35   },  // scroll_depth     (0–100 %)
  f7:  { mean: 1,    std: 2    },  // wishlist_adds    (0–10 typical)
  f8:  { mean: 20,   std: 25   },  // click_count      (0–150 typical)
  f9:  { mean: 0.5,  std: 1    },  // checkout_starts  (0–5 typical)
  f10: { mean: 0.3,  std: 0.6  },  // device_type      (0, 1, 2)
  f11: { mean: 1,    std: 1.5  },  // referral_encoded (0–4)
};

const TRAINING_STD = 10;
const TRAINING_MEAN = 0;

function normalizeForModel(raw: {
  f0: number; f1: number; f2: number; f3: number;
  f4: number; f5: number; f6: number; f7: number;
  f8: number; f9: number; f10: number; f11: number;
}): Record<string, number> {
  const result: Record<string, number> = {};

  for (const [key, value] of Object.entries(raw)) {
    const stat = REAL_STATS[key];
    if (stat && stat.std !== 0) {
      // z-score against real-world → scale to training distribution
      const z = (value - stat.mean) / stat.std;
      result[key] = parseFloat((z * TRAINING_STD + TRAINING_MEAN).toFixed(6));
    } else {
      result[key] = value;
    }
  }

  return result;
}

// ── Network ───────────────────────────────────────────────────────────────────

async function sendDataset(
  payload: Record<string, unknown>,
  accessToken?: string | null
) {
  const API_BASE =
    typeof process !== 'undefined' && process.env?.NEXT_PUBLIC_API_URL
      ? process.env.NEXT_PUBLIC_API_URL
      : 'http://localhost:3001/api';
  try {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };
    if (accessToken) headers['Authorization'] = `Bearer ${accessToken}`;
    await fetch(`${API_BASE}/traceum/dataset`, {
      method: 'POST',
      headers,
      credentials: 'include',
      body: JSON.stringify(payload),
    });
  } catch {
    // fire-and-forget
  }
}

// ── Event tracking ────────────────────────────────────────────────────────────

function track(payload: Record<string, unknown>) {
  const state = getState();
  const f = state.features;
  const event = payload.event as string;

  switch (event) {
    case 'click':
      f.f8_click_count += 1;
      break;
    case 'scroll':
      if (payload.scroll_pct != null) {
        state.scrollSamples.push(payload.scroll_pct as number);
        f.f6_scroll_depth = parseFloat(
          (
            state.scrollSamples.reduce((a, b) => a + b, 0) /
            state.scrollSamples.length
          ).toFixed(2)
        );
      }
      break;
    case 'search':
      f.f4_search_count += 1;
      break;
    case 'product_view':
      f.f3_product_views += 1;
      if (
        payload.category &&
        !state._categoriesSeen.has(payload.category as string)
      ) {
        state._categoriesSeen.add(payload.category as string);
        f.f2_categories_seen = state._categoriesSeen.size;
      }
      break;
    case 'add_to_cart':
      f.f0_cart_items += 1;
      if (payload.value != null)
        f.f1_cart_value = parseFloat(
          (f.f1_cart_value + (payload.value as number)).toFixed(2)
        );
      break;
    case 'remove_from_cart':
      f.f0_cart_items = Math.max(0, f.f0_cart_items - 1);
      if (payload.value != null)
        f.f1_cart_value = parseFloat(
          Math.max(0, f.f1_cart_value - (payload.value as number)).toFixed(2)
        );
      break;
    case 'wishlist_add':
      f.f7_wishlist_adds += 1;
      break;
    case 'checkout_start':
      f.f9_checkout_starts += 1;
      break;
    case 'checkout_complete':
      state._checkoutCompleted = true;
      break;
  }
}

function trackPageView(page: string) {
  const state = getState();
  state._pageViewFired = true;
  const duration_ms = Date.now() - state.pageEnterTime;
  state.pageEnterTime = Date.now();
  track({ event: 'page_view', page, duration_ms });
}

function markCheckoutComplete() {
  getState()._checkoutCompleted = true;
}

// ── Flush ─────────────────────────────────────────────────────────────────────

function flushDataset(accessToken?: string | null) {
  const state = getState();
  const f = state.features;

  // Finalize session duration at flush time
  f.f5_session_duration = Math.round(
    (Date.now() - state.pageEnterTime) / 1000
  );

  // Raw real-world values
  const raw = {
    f0:  f.f0_cart_items,
    f1:  f.f1_cart_value,
    f2:  f.f2_categories_seen,
    f3:  f.f3_product_views,
    f4:  f.f4_search_count,
    f5:  f.f5_session_duration,
    f6:  f.f6_scroll_depth,
    f7:  f.f7_wishlist_adds,
    f8:  f.f8_click_count,
    f9:  f.f9_checkout_starts,
    f10: f.f10_device_type,
    f11: f.f11_referral_encoded,
  };

  // Normalize to match training distribution (mean=0, std=10)
  const normalized = normalizeForModel(raw);

  const payload = {
    // Normalized features (model-ready)
    f0:  normalized.f0,
    f1:  normalized.f1,
    f2:  normalized.f2,
    f3:  normalized.f3,
    f4:  normalized.f4,
    f5:  normalized.f5,
    f6:  normalized.f6,
    f7:  normalized.f7,
    f8:  normalized.f8,
    f9:  normalized.f9,
    f10: normalized.f10,
    f11: normalized.f11,

    // Labels & meta — NOT normalized, used as-is by model
    treatment: f.f9_checkout_starts > 0 ? 1 : 0,
    conversion: state._checkoutCompleted ? 1 : 0,
    exposure: parseFloat(
      Math.min(
        1,
        f.f0_cart_items * 0.1 + f.f3_product_views * 0.05
      ).toFixed(4)
    ),
    visit: state._pageViewFired ? 1 : 0,
    session_id: state.sessionId,
  };

  sendDataset(payload, accessToken).catch(() => {});
}

// ── Utilities ─────────────────────────────────────────────────────────────────

function getFeatureVector() {
  return { ...getState().features };
}

function getSessionId() {
  return getState().sessionId;
}

function resetScrollSamples() {
  getState().scrollSamples = [];
}

export {
  track,
  trackPageView,
  flushDataset,
  markCheckoutComplete,
  getFeatureVector,
  getSessionId,
  resetScrollSamples,
};