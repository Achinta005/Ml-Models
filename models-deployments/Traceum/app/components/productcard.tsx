'use client';
import Image from 'next/image';
import { track } from '@/app/lib/tracker';
import { useCart } from '@/app/lib/cartContext';
import type { Product } from '@/app/lib/cartContext';

interface Props {
  product: Product;
  onClick?: () => void;
}

export function ProductCard({ product, onClick }: Props) {
  const { addToCart } = useCart();

  function handleProductView() {
    track({
      event: 'product_view',
      product_id: product.id,
      category: product.category,
    });
    if (onClick) onClick();
  }

  function handleWishlist(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    track({
      event: 'wishlist_add',
      product_id: product.id,
      category: product.category,
    });
  }

  function handleAddToCart(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    addToCart(product);
  }

  return (
    <div
      onClick={handleProductView}
      className="group flex flex-col bg-[#111] border border-white/5 rounded-xl overflow-hidden hover:border-white/15 transition-colors cursor-pointer"
    >
      {/* Real product image from FakeStore */}
      <div className="relative h-48 bg-white flex items-center justify-center p-4">
        <Image
          src={product.image}
          alt={product.name}
          fill
          className="object-contain p-4"
          sizes="(max-width: 768px) 50vw, 25vw"
        />
        <span className="absolute bottom-2 right-2 text-[10px] font-mono text-white/60 bg-black/50 px-2 py-0.5 rounded-full capitalize">
          {product.category}
        </span>
        <button
          onClick={handleWishlist}
          data-no-track
          className="absolute top-2 right-2 w-7 h-7 flex items-center justify-center rounded-full bg-black/20 text-gray-400 hover:text-red-400 transition-colors text-sm"
          title="Wishlist"
        >
          ♡
        </button>
      </div>

      {/* Info */}
      <div className="p-4 flex flex-col flex-1">
        <p className="text-sm font-medium text-white/80 mb-1 line-clamp-2 leading-snug">
          {product.name}
        </p>
        <p className="text-xs text-white/30 mb-3 line-clamp-2 leading-relaxed flex-1">
          {product.description}
        </p>
        <div className="flex items-center justify-between mt-auto">
          <div>
            <span className="text-base font-semibold tabular-nums">
              ${product.price.toFixed(2)}
            </span>
            <span className="text-xs text-white/25 ml-2">
              ★ {product.rating} ({product.reviews})
            </span>
          </div>
          <button
            onClick={handleAddToCart}
            data-no-track
            className="text-xs px-3 py-1.5 bg-white/10 hover:bg-white/20 rounded-lg transition-colors font-medium"
          >
            + Cart
          </button>
        </div>
      </div>
    </div>
  );
}