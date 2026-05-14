'use client';
import { useEffect } from 'react';
import { useCart } from '@/app/lib/cartContext';
import type { Product } from '@/app/lib/cartContext';

interface ProductModalProps {
  product: Product | null;
  onClose: () => void;
  onAddToCart: (product: Product) => void;
}

export function ProductModal({ product, onClose, onAddToCart }: ProductModalProps) {
  // Close on Escape key
  useEffect(() => {
    if (!product) return;
    function handleKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose();
    }
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [product, onClose]);

  // Lock body scroll when modal is open
  useEffect(() => {
    if (product) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => { document.body.style.overflow = ''; };
  }, [product]);

  if (!product) return null;

  const stars = Math.round(product.rating);

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{
          position: 'fixed', inset: 0, zIndex: 1100,
          background: 'rgba(0,0,0,0.75)',
          backdropFilter: 'blur(8px)',
          animation: 'fadeIn 0.2s ease',
        }}
      />

      {/* Modal */}
      <div style={{
        position: 'fixed', inset: 0, zIndex: 1101,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: 24,
        pointerEvents: 'none',
      }}>
        <div
          style={{
            pointerEvents: 'auto',
            background: '#0f0f1a',
            border: '1px solid rgba(255,255,255,0.08)',
            borderRadius: 20,
            width: '100%',
            maxWidth: 680,
            maxHeight: '90vh',
            overflowY: 'auto',
            boxShadow: '0 40px 100px rgba(0,0,0,0.6), 0 0 0 1px rgba(99,102,241,0.1)',
            animation: 'modalIn 0.25s cubic-bezier(0.34,1.56,0.64,1)',
          }}
        >
          {/* Close button */}
          <button
            data-no-track
            onClick={onClose}
            style={{
              position: 'absolute',
              // We use relative positioning inside the modal instead
            }}
          />

          <div style={{ position: 'relative' }}>
            {/* Close */}
            <button
              data-no-track
              onClick={onClose}
              style={{
                position: 'absolute', top: 16, right: 16, zIndex: 10,
                width: 32, height: 32, borderRadius: '50%',
                background: 'rgba(255,255,255,0.06)',
                border: '1px solid rgba(255,255,255,0.1)',
                color: 'rgba(255,255,255,0.5)',
                cursor: 'pointer', fontSize: 18,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}
            >×</button>

            {/* Content */}
            <div style={{ display: 'flex', gap: 0, flexWrap: 'wrap' }}>

              {/* Image panel */}
              <div style={{
                flex: '0 0 260px',
                background: 'rgba(255,255,255,0.97)',
                borderRadius: '20px 0 0 20px',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                padding: 32, minHeight: 280,
              }}>
                <img
                  src={product.image}
                  alt={product.name}
                  style={{
                    maxWidth: '100%', maxHeight: 220,
                    objectFit: 'contain',
                    filter: 'drop-shadow(0 8px 24px rgba(0,0,0,0.15))',
                  }}
                />
              </div>

              {/* Info panel */}
              <div style={{ flex: 1, minWidth: 240, padding: '32px 28px 28px' }}>

                {/* Category badge */}
                <div style={{
                  display: 'inline-block',
                  padding: '4px 12px', borderRadius: 999,
                  background: 'rgba(99,102,241,0.12)',
                  border: '1px solid rgba(99,102,241,0.25)',
                  color: '#a5b4fc', fontSize: 11,
                  fontFamily: "'DM Mono',monospace",
                  letterSpacing: 1.5, textTransform: 'uppercase',
                  marginBottom: 14,
                }}>
                  {product.category}
                </div>

                {/* Name */}
                <h2 style={{
                  margin: '0 0 12px',
                  fontSize: 20, fontWeight: 700,
                  color: 'rgba(255,255,255,0.9)',
                  lineHeight: 1.3,
                  letterSpacing: '-0.3px',
                  paddingRight: 32,
                }}>
                  {product.name}
                </h2>

                {/* Rating */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 20 }}>
                  <div style={{ display: 'flex', gap: 2 }}>
                    {[1,2,3,4,5].map(i => (
                      <span key={i} style={{ fontSize: 14, color: i <= stars ? '#fbbf24' : 'rgba(255,255,255,0.1)' }}>★</span>
                    ))}
                  </div>
                  <span style={{ color: 'rgba(255,255,255,0.3)', fontSize: 12, fontFamily: "'DM Mono',monospace" }}>
                    {product.rating.toFixed(1)}
                  </span>
                </div>

                {/* Description */}
                {product.description && (
                  <p style={{
                    margin: '0 0 24px',
                    fontSize: 13, lineHeight: 1.65,
                    color: 'rgba(255,255,255,0.4)',
                  }}>
                    {product.description}
                  </p>
                )}

                {/* Divider */}
                <div style={{ height: 1, background: 'rgba(255,255,255,0.05)', marginBottom: 24 }} />

                {/* Price + CTA */}
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
                  <div>
                    <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.25)', fontFamily: "'DM Mono',monospace", marginBottom: 2 }}>price</div>
                    <div style={{ fontSize: 28, fontWeight: 800, color: '#fff', letterSpacing: '-1px' }}>
                      ${product.price.toFixed(2)}
                    </div>
                  </div>

                  <button
                    onClick={() => { onAddToCart(product); onClose(); }}
                    style={{
                      padding: '12px 24px',
                      background: 'linear-gradient(135deg,#6366f1,#8b5cf6)',
                      border: 'none', borderRadius: 12,
                      color: '#fff', fontSize: 14, fontWeight: 600,
                      cursor: 'pointer', whiteSpace: 'nowrap',
                      boxShadow: '0 4px 20px rgba(99,102,241,0.35)',
                      transition: 'transform 0.1s, box-shadow 0.1s',
                    }}
                    onMouseEnter={e => {
                      (e.currentTarget as HTMLButtonElement).style.transform = 'translateY(-1px)';
                      (e.currentTarget as HTMLButtonElement).style.boxShadow = '0 6px 28px rgba(99,102,241,0.5)';
                    }}
                    onMouseLeave={e => {
                      (e.currentTarget as HTMLButtonElement).style.transform = '';
                      (e.currentTarget as HTMLButtonElement).style.boxShadow = '0 4px 20px rgba(99,102,241,0.35)';
                    }}
                  >
                    Add to Cart →
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <style>{`
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
        @keyframes modalIn {
          from { opacity: 0; transform: scale(0.92) translateY(16px); }
          to   { opacity: 1; transform: scale(1) translateY(0); }
        }
      `}</style>
    </>
  );
}