import React from 'react';
import { useTheme } from '../../../hooks/useTheme';
import type { Theme } from '../../../hooks/useTheme';
import './ThemeToggle.css';

export interface ThemeToggleProps {
  'aria-label'?: string;
}

const CYCLE_ORDER: Theme[] = ['light', 'dark', 'system'];

export const ThemeToggle: React.FC<ThemeToggleProps> = ({
  'aria-label': ariaLabel,
}) => {
  const { theme, resolvedTheme, setTheme } = useTheme();

  const handleClick = () => {
    const currentIndex = CYCLE_ORDER.indexOf(theme);
    const nextIndex = (currentIndex + 1) % CYCLE_ORDER.length;
    setTheme(CYCLE_ORDER[nextIndex]);
  };

  const icon = resolvedTheme === 'dark' ? '🌙' : '☀️';
  const label =
    ariaLabel ??
    `テーマ切替（現在: ${theme === 'system' ? 'システム' : theme === 'dark' ? 'ダーク' : 'ライト'}）`;

  return (
    <button
      type="button"
      className="theme-toggle"
      onClick={handleClick}
      aria-label={label}
      title={label}
    >
      <span className="theme-toggle__icon" aria-hidden="true">
        {icon}
      </span>
    </button>
  );
};

export default ThemeToggle;
