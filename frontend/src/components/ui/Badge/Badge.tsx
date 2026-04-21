import React from 'react';
import './Badge.css';

export interface BadgeProps {
  variant: 'success' | 'warning' | 'danger' | 'info' | 'neutral';
  size?: 'sm' | 'md';
  title?: string;
  children: React.ReactNode;
}

export const Badge: React.FC<BadgeProps> = ({
  variant,
  size = 'md',
  title,
  children,
}) => {
  const classes = ['badge', `badge--${variant}`, `badge--${size}`].join(' ');

  return (
    <span className={classes} role="status" title={title}>
      {children}
    </span>
  );
};

export default Badge;
