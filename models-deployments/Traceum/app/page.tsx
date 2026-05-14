// app/page.tsx
import Link from 'next/link';

export default function HomePage() { 
  return (
    <main className="min-h-screen bg-[#0a0a0a] text-white">
      {/* Nav */}
      <nav className="flex items-center justify-between px-6 py-4 border-b border-white/5">
        <span className="font-mono text-sm tracking-widest text-white/40 uppercase">Traceum</span>
        <div className="flex items-center gap-4">
          <Link href="/login" className="text-sm text-white/50 hover:text-white transition-colors">
            Sign in
          </Link>
          <Link
            href="/register"
            className="text-sm px-4 py-1.5 bg-white text-black rounded-md font-medium hover:bg-white/90 transition-colors"
          >
            Get started
          </Link>
        </div>
      </nav>

      {/* Hero */}
      <section className="max-w-3xl mx-auto px-6 pt-24 pb-16">
        <div className="inline-flex items-center gap-2 text-xs font-mono text-white/30 border border-white/10 rounded-full px-3 py-1 mb-8">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
          Real-time behavioral tracking
        </div>

        <h1 className="text-5xl font-semibold leading-tight tracking-tight mb-6">
          Know who&apos;s about to buy.{' '}
          <span className="text-white/25">Before they do.</span>
        </h1>

        <p className="text-white/40 text-lg leading-relaxed mb-10 max-w-xl">
          Traceum streams user behavior into a live ML model and predicts purchase intent in real time — so you can show the right offer at the right moment.
        </p>

        <div className="flex items-center gap-3">
          <Link
            href="/register"
            className="px-5 py-2.5 bg-white text-black text-sm font-medium rounded-md hover:bg-white/90 transition-colors"
          >
            Start tracking free
          </Link>
          <Link
            href="/login"
            className="px-5 py-2.5 text-sm text-white/50 hover:text-white border border-white/10 rounded-md transition-colors"
          >
            Sign in →
          </Link>
        </div>
      </section>

      {/* Feature grid */}
      <section className="max-w-3xl mx-auto px-6 pb-24">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-px bg-white/5 border border-white/5 rounded-xl overflow-hidden">
          {[
            {
              label: 'f0–f11 Features',
              desc: 'Cart value, scroll depth, session time, clicks — 12 live signals per user.',
            },
            {
              label: 'PSM Scoring',
              desc: 'FastAPI model returns a propensity score per session within milliseconds.',
            },
            {
              label: 'Outcome Tracking',
              desc: 'Conversion events close the loop for weekly automated retraining.',
            },
          ].map((f) => (
            <div key={f.label} className="bg-[#0a0a0a] p-6">
              <p className="text-xs font-mono text-white/30 mb-3 uppercase tracking-wider">{f.label}</p>
              <p className="text-sm text-white/55 leading-relaxed">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Feature vector preview */}
      <section className="max-w-3xl mx-auto px-6 pb-24">
        <p className="text-xs font-mono text-white/20 mb-4 uppercase tracking-wider">Live feature vector sample</p>
        <div className="bg-[#111] border border-white/5 rounded-xl p-5 font-mono text-xs text-white/40 overflow-x-auto">
          <pre>{`session_id: "a3f9b2c1..."
feature_vector: [
  2,      // f0: cart_items
  84.99,  // f1: cart_value
  3,      // f2: categories_seen
  7,      // f3: product_views
  2,      // f4: search_count
  312,    // f5: session_duration (s)
  68.4,   // f6: scroll_depth (avg %)
  1,      // f7: wishlist_adds
  24,     // f8: click_count
  1,      // f9: checkout_starts
  0,      // f10: device_type (desktop)
  1       // f11: referral_encoded (organic)
]
propensity_score: 0.847`}</pre>
        </div>
      </section>

      <footer className="border-t border-white/5 px-6 py-6 text-center text-xs text-white/20 font-mono">
        © {new Date().getFullYear()} Traceum — behavioral intelligence for ecommerce
      </footer>
    </main>
  );
}