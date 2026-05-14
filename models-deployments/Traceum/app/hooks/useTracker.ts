'use client';
import { useEffect, useRef } from 'react';
import { useAuth } from '@/app/context/authContext';
import { track, trackPageView, resetScrollSamples, flushDataset } from '../lib/tracker';

interface UseTrackerOptions {
  page: string;
  isProductPage?: boolean;
}

export function useTracker({ page, isProductPage = false }: UseTrackerOptions) {
  const { accessToken } = useAuth();
  const scrollThresholdsFired = useRef<Set<number>>(new Set());
  const lastScrollTime = useRef<number>(0);

  useEffect(() => {
    trackPageView(page);
    resetScrollSamples();
    scrollThresholdsFired.current = new Set();

    const THROTTLE_MS = 500;
    const THRESHOLDS = [25, 50, 75, 100];

    function handleScroll() {
      const now = Date.now();
      if (now - lastScrollTime.current < THROTTLE_MS) return;
      lastScrollTime.current = now;

      const scrolled = window.scrollY + window.innerHeight;
      const total = document.documentElement.scrollHeight;
      const pct = Math.min(100, Math.round((scrolled / total) * 100));

      for (const threshold of THRESHOLDS) {
        if (pct >= threshold && !scrollThresholdsFired.current.has(threshold)) {
          scrollThresholdsFired.current.add(threshold);
          track({ event: 'scroll', page, scroll_pct: threshold });
        }
      }
    }

    function handleClick(e: MouseEvent) {
      const target = e.target as HTMLElement;
      if (target.closest('[data-no-track]')) return;
      track({
        event: 'click',
        page,
        metadata: {
          tag: target.tagName,
          text: target.innerText?.slice(0, 40),
        },
      });
    }

    function handleSessionEnd() {
      flushDataset(accessToken);
    }

    window.addEventListener('scroll', handleScroll, { passive: true });
    document.addEventListener('click', handleClick);
    window.addEventListener('beforeunload', handleSessionEnd);

    return () => {
      window.removeEventListener('scroll', handleScroll);
      document.removeEventListener('click', handleClick);
      window.removeEventListener('beforeunload', handleSessionEnd);
    };
  }, [page, accessToken]);
}