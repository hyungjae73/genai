import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import Rules from '../Rules';

describe('Rules - Help Modal', () => {
  it('should display help button with correct aria-label', () => {
    render(<Rules />);

    const helpButton = screen.getByRole('button', { name: 'ヘルプを表示' });
    expect(helpButton).toBeInTheDocument();
    expect(helpButton).toHaveTextContent('?');
  });

  it('should open help modal with rules content when help button is clicked', async () => {
    render(<Rules />);

    const helpButton = screen.getByRole('button', { name: 'ヘルプを表示' });
    await userEvent.click(helpButton);

    expect(screen.getByText('チェックルールの使い方')).toBeInTheDocument();
    expect(screen.getByText('監視システムがどのような項目をチェックしているか確認したい')).toBeInTheDocument();
    expect(screen.getByText('カテゴリフィルター')).toBeInTheDocument();
    expect(screen.getByText('重要度と有効/無効')).toBeInTheDocument();
    expect(screen.getByText('5つのカテゴリ')).toBeInTheDocument();
  });
});
