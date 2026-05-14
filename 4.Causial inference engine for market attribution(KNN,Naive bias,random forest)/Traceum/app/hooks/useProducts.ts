'use client';
import { useState, useEffect } from 'react';
import type { Product } from '@/app/lib/cartContext';

interface FakeStoreProduct {
  id: number;
  title: string;
  price: number;
  category: string;
  description: string;
  image: string;
  rating: { rate: number; count: number };
}

// Map FakeStore → your Product shape
function mapProduct(p: FakeStoreProduct): Product {
  return {
    id: String(p.id),
    name: p.title,
    price: p.price,
    category: p.category,
    description: p.description,
    image: p.image,          // real image URL from FakeStore
    rating: p.rating.rate,
    reviews: p.rating.count,
  };
}

export function useProducts() {
  const [products, setProducts] = useState<Product[]>([]);
  const [categories, setCategories] = useState<string[]>(['All']);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const [productsRes, categoriesRes] = await Promise.all([
          fetch('https://fakestoreapi.com/products'),
          fetch('https://fakestoreapi.com/products/categories'),
        ]);

        if (!productsRes.ok || !categoriesRes.ok)
          throw new Error('FakeStore API error');

        const rawProducts: FakeStoreProduct[] = await productsRes.json();
        const rawCategories: string[] = await categoriesRes.json();

        setProducts(rawProducts.map(mapProduct));
        setCategories(['All', ...rawCategories]);
      } catch (err: any) {
        setError(err.message ?? 'Failed to load products');
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  return { products, categories, loading, error };
}