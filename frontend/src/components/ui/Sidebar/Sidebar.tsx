import React, { useCallback } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import './Sidebar.css';

export interface NavItem {
  path: string;
  label: string;
  icon?: React.ReactNode;
  group: string;
}

export interface SidebarProps {
  items: NavItem[];
  groups: { key: string; label: string }[];
  collapsed?: boolean;
  onToggle?: () => void;
  hoverExpanded?: boolean;
}

export const Sidebar: React.FC<SidebarProps> = ({
  items,
  groups,
  collapsed = false,
  onToggle,
  hoverExpanded = false,
}) => {
  const location = useLocation();
  const showLabels = !collapsed || hoverExpanded;

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Escape' && onToggle) {
        onToggle();
      }
    },
    [onToggle],
  );

  const groupedItems = groups
    .map((group) => ({
      ...group,
      items: items.filter((item) => item.group === group.key),
    }))
    .filter((group) => group.items.length > 0);

  return (
    <nav
      className={`sidebar${collapsed ? ' sidebar--collapsed' : ''}${hoverExpanded ? ' sidebar--hover-expanded' : ''}`}
      aria-label="メインナビゲーション"
      onKeyDown={handleKeyDown}
    >
      {onToggle && (
        <button
          className="sidebar__toggle"
          onClick={onToggle}
          aria-label={collapsed ? 'サイドバーを展開' : 'サイドバーを折りたたむ'}
          type="button"
        >
          <span className="sidebar__toggle-icon" aria-hidden="true">
            {collapsed ? '▶' : '◀'}
          </span>
        </button>
      )}

      {groupedItems.map((group, groupIndex) => (
        <div key={group.key} className="sidebar__group" role="group" aria-label={group.label}>
          {showLabels && (
            <h3 className="sidebar__group-label">{group.label}</h3>
          )}

          <ul className="sidebar__list" role="list">
            {group.items.map((item) => {
              const isActive = location.pathname === item.path;
              return (
                <li key={item.path} className="sidebar__item" role="listitem">
                  <NavLink
                    to={item.path}
                    className={`sidebar__link${isActive ? ' sidebar__link--active' : ''}`}
                    aria-current={isActive ? 'page' : undefined}
                    title={collapsed && !hoverExpanded ? item.label : undefined}
                  >
                    {item.icon && (
                      <span className="sidebar__icon" aria-hidden="true">
                        {item.icon}
                      </span>
                    )}
                    {showLabels && (
                      <span className="sidebar__label">{item.label}</span>
                    )}
                  </NavLink>
                </li>
              );
            })}
          </ul>

          {groupIndex < groupedItems.length - 1 && (
            <hr className="sidebar__divider" />
          )}
        </div>
      ))}
    </nav>
  );
};

export default Sidebar;
