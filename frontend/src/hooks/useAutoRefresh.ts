import { useEffect, useRef } from 'react';

/**
 * Custom hook for auto-refreshing data at specified intervals
 * @param callback - Function to call on each refresh
 * @param interval - Refresh interval in milliseconds (default: 30000ms = 30s)
 */
export const useAutoRefresh = (callback: () => void, interval: number = 30000) => {
  const savedCallback = useRef<() => void>(callback);

  // Remember the latest callback
  useEffect(() => {
    savedCallback.current = callback;
  }, [callback]);

  // Set up the interval
  useEffect(() => {
    const tick = () => {
      if (savedCallback.current) {
        savedCallback.current();
      }
    };

    const id = setInterval(tick, interval);
    return () => clearInterval(id);
  }, [interval]);
};
