'use client';
import {
  createContext,
  useContext,
  useState,
  useCallback,
  ReactNode,
} from 'react';
import { track } from './tracker';

export interface Product {
  id: string;
  name: string;
  price: number;
  category: string;
  image: string;
  description: string;
  rating: number;
  reviews: number;
}

interface CartItem {
  product: Product;
  qty: number;
}

interface CartContextType {
  items: CartItem[];
  totalItems: number;
  totalValue: number;
  addToCart: (product: Product) => void;
  removeFromCart: (product: Product) => void;
  clearCart: () => void;
}

const CartContext = createContext<CartContextType | null>(null);

function CartProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<CartItem[]>([]);

  const totalItems = items.reduce((s, i) => s + i.qty, 0);
  const totalValue = parseFloat(
    items.reduce((s, i) => s + i.product.price * i.qty, 0).toFixed(2)
  );

  const addToCart = useCallback((product: Product) => {
    setItems((prev) => {
      const ex = prev.find((i) => i.product.id === product.id);
      return ex
        ? prev.map((i) =>
            i.product.id === product.id ? { ...i, qty: i.qty + 1 } : i
          )
        : [...prev, { product, qty: 1 }];
    });
    track({
      event: 'add_to_cart',
      product_id: product.id,
      category: product.category,
      value: product.price,
    });
  }, []);

  const removeFromCart = useCallback((product: Product) => {
    setItems((prev) => {
      const ex = prev.find((i) => i.product.id === product.id);
      if (!ex) return prev;
      if (ex.qty === 1) return prev.filter((i) => i.product.id !== product.id);
      return prev.map((i) =>
        i.product.id === product.id ? { ...i, qty: i.qty - 1 } : i
      );
    });
    track({
      event: 'remove_from_cart',
      product_id: product.id,
      category: product.category,
      value: product.price,
    });
  }, []);

  const clearCart = useCallback(() => setItems([]), []);

  return (
    <CartContext.Provider
      value={{ items, totalItems, totalValue, addToCart, removeFromCart, clearCart }}
    >
      {children}
    </CartContext.Provider>
  );
}

function useCart() {
  const ctx = useContext(CartContext);
  if (!ctx) throw new Error('useCart must be inside CartProvider');
  return ctx;
}

export { CartProvider, useCart };