import { describe, it, expect, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { HelpButton } from './HelpButton';

describe('HelpButton', () => {
  afterEach(cleanup);

  it('renders a "?" button', () => {
    render(<HelpButton title="ヘルプ">コンテンツ</HelpButton>);
    const button = screen.getByRole('button', { name: 'ヘルプを表示' });
    expect(button).toBeInTheDocument();
    expect(button.textContent).toBe('?');
  });

  it('has aria-label="ヘルプを表示" for screen readers', () => {
    render(<HelpButton title="ヘルプ">コンテンツ</HelpButton>);
    const button = screen.getByRole('button', { name: 'ヘルプを表示' });
    expect(button).toHaveAttribute('aria-label', 'ヘルプを表示');
  });

  it('does not show the modal initially', () => {
    render(<HelpButton title="ヘルプ">コンテンツ</HelpButton>);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('opens the modal with title and children when clicked', () => {
    render(
      <HelpButton title="使い方ガイド">
        <p>ヘルプの説明文</p>
      </HelpButton>
    );

    fireEvent.click(screen.getByRole('button', { name: 'ヘルプを表示' }));

    const dialog = screen.getByRole('dialog');
    expect(dialog).toBeInTheDocument();
    expect(screen.getByText('使い方ガイド')).toBeInTheDocument();
    expect(screen.getByText('ヘルプの説明文')).toBeInTheDocument();
  });

  it('closes the modal when the close button is clicked', () => {
    render(<HelpButton title="ヘルプ">コンテンツ</HelpButton>);

    fireEvent.click(screen.getByRole('button', { name: 'ヘルプを表示' }));
    expect(screen.getByRole('dialog')).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText('Close'));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('closes the modal when Escape key is pressed', () => {
    render(<HelpButton title="ヘルプ">コンテンツ</HelpButton>);

    fireEvent.click(screen.getByRole('button', { name: 'ヘルプを表示' }));
    expect(screen.getByRole('dialog')).toBeInTheDocument();

    fireEvent.keyDown(screen.getByRole('dialog').parentElement!, {
      key: 'Escape',
    });
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('applies the help-button CSS class', () => {
    render(<HelpButton title="ヘルプ">コンテンツ</HelpButton>);
    const button = screen.getByRole('button', { name: 'ヘルプを表示' });
    expect(button).toHaveClass('help-button');
  });
});
