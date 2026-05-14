'use client';
import { useState, useCallback, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import { track, markCheckoutComplete, flushDataset } from '@/app/lib/tracker';
import { CartProvider, useCart } from '@/app/lib/cartContext';
import type { Product } from '@/app/lib/cartContext';
import { useTracker } from '@/app/hooks/useTracker';
import { useProducts } from '@/app/hooks/useProducts';
import { ProductCard } from '../components/productcard';
import { ProductModal } from '../components/productModal';
import { FeatureDebug } from '../components/featureDebug';
import { useAuth } from '@/app/context/authContext';

// ── Cart Drawer ───────────────────────────────────────────────────────────────
function CartDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { items, totalValue, addToCart, removeFromCart, clearCart } = useCart();
  const { accessToken } = useAuth();

  function handleCheckout() {
    track({ event: 'checkout_start', value: totalValue });
    markCheckoutComplete();
    flushDataset(accessToken);       // flush immediately on checkout
    alert('Checkout complete! Data saved.');
    clearCart();
    onClose();
  }

  return (
    <>
      {open && (
        <div
          onClick={onClose}
          style={{
            position: 'fixed', inset: 0,
            background: 'rgba(0,0,0,0.6)', zIndex: 998,
            backdropFilter: 'blur(4px)',
          }}
        />
      )}
      <div style={{
        position: 'fixed', top: 0, right: 0, height: '100vh', width: 380,
        zIndex: 999, background: '#0d0d12',
        borderLeft: '1px solid rgba(255,255,255,0.07)',
        transform: open ? 'translateX(0)' : 'translateX(100%)',
        transition: 'transform 0.35s cubic-bezier(0.4,0,0.2,1)',
        display: 'flex', flexDirection: 'column',
      }}>
        {/* Header */}
        <div style={{
          padding: '24px 24px 16px',
          borderBottom: '1px solid rgba(255,255,255,0.06)',
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        }}>
          <span style={{ color: '#fff', fontSize: 15, fontWeight: 600 }}>
            Cart ({items.reduce((s, i) => s + i.qty, 0)})
          </span>
          <button data-no-track onClick={onClose} style={{ background: 'none', border: 'none', color: 'rgba(255,255,255,0.3)', cursor: 'pointer', fontSize: 20 }}>×</button>
        </div>

        {/* Items */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '16px 24px' }}>
          {items.length === 0 ? (
            <div style={{ color: 'rgba(255,255,255,0.2)', fontSize: 13, textAlign: 'center', marginTop: 60 }}>
              Your cart is empty
            </div>
          ) : items.map(({ product, qty }) => (
            <div key={product.id} style={{
              display: 'flex', gap: 12, marginBottom: 16, padding: 12,
              background: 'rgba(255,255,255,0.03)', borderRadius: 10,
              border: '1px solid rgba(255,255,255,0.05)',
            }}>
              <img src={product.image} alt={product.name} style={{ width: 48, height: 48, objectFit: 'contain', background: '#fff', borderRadius: 8, padding: 4, flexShrink: 0 }} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ color: 'rgba(255,255,255,0.8)', fontSize: 13, fontWeight: 500, marginBottom: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{product.name}</div>
                <div style={{ color: 'rgba(255,255,255,0.35)', fontSize: 12 }}>${product.price.toFixed(2)} × {qty}</div>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4, alignItems: 'center' }}>
                <button data-no-track onClick={() => { track({ event: 'add_to_cart', value: product.price }); addToCart(product); }} style={qtyBtn}>+</button>
                <button data-no-track onClick={() => { track({ event: 'remove_from_cart', value: product.price }); removeFromCart(product); }} style={qtyBtn}>−</button>
              </div>
            </div>
          ))}
        </div>

        {/* Footer */}
        {items.length > 0 && (
          <div style={{ padding: '16px 24px 28px', borderTop: '1px solid rgba(255,255,255,0.06)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
              <span style={{ color: 'rgba(255,255,255,0.4)', fontSize: 13 }}>Total</span>
              <span style={{ color: '#fff', fontSize: 16, fontWeight: 700 }}>${totalValue.toFixed(2)}</span>
            </div>
            <button onClick={handleCheckout} style={{
              width: '100%', padding: '13px 0',
              background: 'linear-gradient(135deg,#6366f1,#8b5cf6)',
              border: 'none', borderRadius: 10, color: '#fff',
              fontSize: 14, fontWeight: 600, cursor: 'pointer',
            }}>
              Checkout →
            </button>
            <button data-no-track onClick={clearCart} style={{
              width: '100%', marginTop: 8, padding: '10px 0',
              background: 'none', border: '1px solid rgba(255,255,255,0.08)',
              borderRadius: 10, color: 'rgba(255,255,255,0.3)',
              fontSize: 13, cursor: 'pointer',
            }}>
              Clear cart
            </button>
          </div>
        )}
      </div>
    </>
  );
}

const qtyBtn: React.CSSProperties = {
  width: 24, height: 24, background: 'rgba(255,255,255,0.06)',
  border: '1px solid rgba(255,255,255,0.1)', borderRadius: 6,
  color: 'rgba(255,255,255,0.5)', cursor: 'pointer', fontSize: 14,
  display: 'flex', alignItems: 'center', justifyContent: 'center',
};

// ── Store Page ────────────────────────────────────────────────────────────────
function StorePage() {
  const router = useRouter();
  useTracker({ page: '/dashboard/store' });

  const { totalItems, totalValue } = useCart();
  const { products, categories, loading, error } = useProducts();

  const [cartOpen, setCartOpen] = useState(false);
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [activeCategory, setActiveCategory] = useState('All');
  const [searchQuery, setSearchQuery] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [sortBy, setSortBy] = useState('default');
  const [toasts, setToasts] = useState<{ id: number; msg: string }[]>([]);

  const addToast = useCallback((msg: string) => {
    const id = Date.now();
    setToasts((t) => [...t, { id, msg }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 2200);
  }, []);

  const { addToCart } = useCart();

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!searchInput.trim()) return;
    track({ event: 'search', page: '/dashboard/store', metadata: { query: searchInput.trim() } });
    setSearchQuery(searchInput.trim());
  }

  function handleAddToCart(product: Product) {
    track({ event: 'add_to_cart', value: product.price });
    addToCart(product);
    addToast(`${product.name.slice(0, 30)}… added`);
  }

  const filtered = useMemo(() => {
    let list = products
      .filter((p) => activeCategory === 'All' || p.category === activeCategory)
      .filter((p) =>
        !searchQuery ||
        p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        p.category.toLowerCase().includes(searchQuery.toLowerCase())
      );

    if (sortBy === 'price_asc') list = [...list].sort((a, b) => a.price - b.price);
    if (sortBy === 'price_desc') list = [...list].sort((a, b) => b.price - a.price);
    if (sortBy === 'rating') list = [...list].sort((a, b) => b.rating - a.rating);

    return list;
  }, [products, activeCategory, searchQuery, sortBy]);

  return (
    <div style={{ minHeight: '100vh', background: '#080810', color: '#fff', fontFamily: "'DM Sans',sans-serif" }}>

      {/* Nav */}
      <nav style={{
        position: 'sticky', top: 0, zIndex: 500,
        background: 'rgba(8,8,16,0.85)', backdropFilter: 'blur(20px)',
        borderBottom: '1px solid rgba(255,255,255,0.05)', padding: '0 24px',
      }}>
        <div style={{ maxWidth: 1200, margin: '0 auto', height: 60, display: 'flex', alignItems: 'center', gap: 20 }}>
          <div style={{ fontFamily: "'DM Mono',monospace", fontSize: 13, letterSpacing: 4, color: 'rgba(255,255,255,0.35)', textTransform: 'uppercase', flexShrink: 0 }}>
            Traceum<span style={{ color: '#6366f1' }}>.</span>
          </div>

          <form onSubmit={handleSearch} style={{ flex: 1, maxWidth: 380 }}>
            <div style={{ position: 'relative' }}>
              <span style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: 'rgba(255,255,255,0.2)', fontSize: 14, pointerEvents: 'none' }}>⌕</span>
              <input
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                placeholder="Search products…"
                style={{
                  width: '100%', boxSizing: 'border-box',
                  background: 'rgba(255,255,255,0.04)',
                  border: '1px solid rgba(255,255,255,0.08)',
                  borderRadius: 10, padding: '8px 12px 8px 34px',
                  color: 'rgba(255,255,255,0.7)', fontSize: 13, outline: 'none',
                }}
              />
            </div>
          </form>

          <div style={{ marginLeft: 'auto', display: 'flex', gap: 12, alignItems: 'center' }}>
            <button data-no-track onClick={() => router.push('/predict')} style={{
              background: 'rgba(99,102,241,0.12)',
              border: '1px solid rgba(99,102,241,0.3)', borderRadius: 10,
              padding: '8px 16px', color: '#a5b4fc', cursor: 'pointer',
              fontSize: 13, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6,
            }}>
              📊 Predictions
            </button>
            <button data-no-track onClick={() => setCartOpen(true)} style={{
              position: 'relative', background: 'rgba(99,102,241,0.12)',
              border: '1px solid rgba(99,102,241,0.3)', borderRadius: 10,
              padding: '8px 16px', color: '#a5b4fc', cursor: 'pointer',
              fontSize: 13, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6,
            }}>
              🛒 Cart
              {totalItems > 0 && (
                <span style={{
                  position: 'absolute', top: -7, right: -7,
                  background: '#6366f1', color: '#fff', borderRadius: '50%',
                  width: 18, height: 18, fontSize: 10, fontWeight: 700,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>{totalItems}</span>
              )}
            </button>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <div style={{ borderBottom: '1px solid rgba(255,255,255,0.04)', padding: '48px 24px 40px' }}>
        <div style={{ maxWidth: 1200, margin: '0 auto' }}>
          <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', flexWrap: 'wrap', gap: 20 }}>
            <div>
              <div style={{ fontFamily: "'DM Mono',monospace", fontSize: 11, letterSpacing: 3, color: 'rgba(99,102,241,0.7)', textTransform: 'uppercase', marginBottom: 10 }}>
                {loading ? 'Loading…' : `${filtered.length} products`}
              </div>
              <h1 style={{ fontSize: 'clamp(28px,4vw,44px)', fontWeight: 800, letterSpacing: '-1.5px', margin: 0, lineHeight: 1.1 }}>
                Discover our<br />
                <span style={{ backgroundImage: 'linear-gradient(135deg,#6366f1,#a78bfa,#ec4899)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
                  curated store
                </span>
              </h1>
            </div>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.25)', fontFamily: "'DM Mono',monospace" }}>sort:</span>
              {([['default', 'Default'], ['price_asc', '$ Low'], ['price_desc', '$ High'], ['rating', 'Rating']] as const).map(([v, label]) => (
                <button data-no-track key={v} onClick={() => setSortBy(v)} style={{
                  padding: '5px 12px', borderRadius: 8, fontSize: 12, cursor: 'pointer',
                  background: sortBy === v ? 'rgba(99,102,241,0.2)' : 'rgba(255,255,255,0.04)',
                  border: `1px solid ${sortBy === v ? 'rgba(99,102,241,0.5)' : 'rgba(255,255,255,0.08)'}`,
                  color: sortBy === v ? '#a5b4fc' : 'rgba(255,255,255,0.3)',
                }}>{label}</button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Category pills */}
      <div style={{ borderBottom: '1px solid rgba(255,255,255,0.04)', overflowX: 'auto' }}>
        <div style={{ maxWidth: 1200, margin: '0 auto', padding: '14px 24px', display: 'flex', gap: 8 }}>
          {categories.map((cat) => (
            <button data-no-track key={cat} onClick={() => { setActiveCategory(cat); setSearchQuery(''); setSearchInput(''); }} style={{
              flexShrink: 0, padding: '6px 16px', borderRadius: 999, fontSize: 13,
              cursor: 'pointer', fontWeight: activeCategory === cat ? 600 : 400,
              background: activeCategory === cat ? 'rgba(99,102,241,0.2)' : 'rgba(255,255,255,0.04)',
              border: `1px solid ${activeCategory === cat ? 'rgba(99,102,241,0.45)' : 'rgba(255,255,255,0.07)'}`,
              color: activeCategory === cat ? '#c7d2fe' : 'rgba(255,255,255,0.35)',
              textTransform: 'capitalize',
            }}>{cat}</button>
          ))}
        </div>
      </div>

      {/* Grid */}
      <div style={{ maxWidth: 1200, margin: '0 auto', padding: '32px 24px 120px' }}>
        {error && (
          <div style={{ textAlign: 'center', padding: '60px 0', color: 'rgba(255,100,100,0.6)', fontSize: 14 }}>
            Failed to load products: {error}
          </div>
        )}
        {loading && !error && (
          <div style={{ textAlign: 'center', padding: '80px 0', color: 'rgba(255,255,255,0.2)', fontSize: 14 }}>
            Loading products from FakeStore API…
          </div>
        )}
        {!loading && searchQuery && (
          <div style={{ marginBottom: 20, color: 'rgba(255,255,255,0.3)', fontSize: 13 }}>
            {filtered.length} result{filtered.length !== 1 ? 's' : ''} for "{searchQuery}"
            <button data-no-track onClick={() => { setSearchQuery(''); setSearchInput(''); }} style={{ marginLeft: 10, background: 'none', border: 'none', color: 'rgba(99,102,241,0.7)', cursor: 'pointer', fontSize: 13 }}>Clear</button>
          </div>
        )}
        {!loading && filtered.length === 0 && !error && (
          <div style={{ textAlign: 'center', padding: '80px 0', color: 'rgba(255,255,255,0.15)', fontSize: 15 }}>No products found.</div>
        )}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(220px,1fr))', gap: 20 }}>
          {filtered.map((product) => (
            <ProductCard
              key={product.id}
              product={product}
              onClick={() => setSelectedProduct(product)}
            />
          ))}
        </div>
      </div>

      {/* Sticky cart bar */}
      {totalItems > 0 && (
        <div style={{
          position: 'fixed', bottom: 0, left: 0, right: 0, zIndex: 490,
          background: 'rgba(10,10,20,0.95)', borderTop: '1px solid rgba(99,102,241,0.2)',
          backdropFilter: 'blur(20px)', padding: '14px 24px',
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        }}>
          <div style={{ fontFamily: "'DM Mono',monospace", fontSize: 12, color: 'rgba(255,255,255,0.4)' }}>
            <span style={{ color: '#a5b4fc', fontWeight: 700 }}>{totalItems}</span> item{totalItems !== 1 ? 's' : ''} · <span style={{ color: '#fff' }}>${totalValue.toFixed(2)}</span>
          </div>
          <button data-no-track onClick={() => setCartOpen(true)} style={{
            background: 'linear-gradient(135deg,#6366f1,#8b5cf6)', border: 'none',
            borderRadius: 8, padding: '8px 20px', color: '#fff',
            fontSize: 13, fontWeight: 600, cursor: 'pointer',
          }}>View Cart →</button>
        </div>
      )}

      {/* Toasts */}
      <div style={{ position: 'fixed', top: 20, right: 20, zIndex: 1000, display: 'flex', flexDirection: 'column', gap: 8 }}>
        {toasts.map((t) => (
          <div key={t.id} style={{
            background: 'rgba(20,20,35,0.95)', border: '1px solid rgba(99,102,241,0.35)',
            borderRadius: 10, padding: '10px 16px', fontSize: 13, color: 'rgba(255,255,255,0.75)',
            boxShadow: '0 8px 32px rgba(0,0,0,0.4)', animation: 'slideIn 0.2s ease',
          }}>
            ✓ {t.msg}
          </div>
        ))}
      </div>

      <ProductModal
        product={selectedProduct}
        onClose={() => setSelectedProduct(null)}
        onAddToCart={handleAddToCart}
      />
      <CartDrawer open={cartOpen} onClose={() => setCartOpen(false)} />
      <FeatureDebug />

      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&family=DM+Mono&display=swap');
        * { box-sizing: border-box; }
        ::-webkit-scrollbar { width: 4px; height: 4px; }
        ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 2px; }
        @keyframes slideIn { from { opacity:0; transform:translateX(20px); } to { opacity:1; transform:none; } }
      `}</style>
    </div>
  );
}

export default function App() {
  return (
    <CartProvider>
      <StorePage />
    </CartProvider>
  );
}