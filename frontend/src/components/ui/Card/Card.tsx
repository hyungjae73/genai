import React from 'react';
import './Card.css';

export interface CardProps {
  padding?: 'sm' | 'md' | 'lg';
  borderLeft?: 'success' | 'warning' | 'danger' | 'info';
  hoverable?: boolean;
  children: React.ReactNode;
  className?: string;
}

export const Card: React.FC<CardProps> = ({
  padding = 'md',
  borderLeft,
  hoverable = false,
  children,
  className,
}) => {
  const classes = [
    'card',
    `card--pad-${padding}`,
    borderLeft ? `card--border-${borderLeft}` : '',
    hoverable ? 'card--hoverable' : '',
    className ?? '',
  ]
    .filter(Boolean)
    .join(' ');

  return <div className={classes}>{children}</div>;
};

export default Card;
