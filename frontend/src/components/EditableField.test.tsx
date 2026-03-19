/**
 * Unit tests for EditableField component.
 *
 * Tests cover:
 * - Inline editing flow (click edit → type → save/cancel)
 * - Validation for number and currency field types
 * - Manual edit indicator display
 * - Keyboard shortcuts (Enter to save, Escape to cancel)
 * - Error handling on save failure
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import EditableField from './EditableField';

describe('EditableField', () => {
  let onSave: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    onSave = vi.fn().mockResolvedValue(undefined);
  });

  /* ---------------------------------------------------------------- */
  /*  Display mode                                                     */
  /* ---------------------------------------------------------------- */
  it('renders the current value and an edit button', () => {
    render(<EditableField value="テスト値" onSave={onSave} />);
    expect(screen.getByText('テスト値')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /編集/ })).toBeInTheDocument();
  });

  it('shows dash placeholder when value is empty', () => {
    render(<EditableField value="" onSave={onSave} />);
    expect(screen.getByText('—')).toBeInTheDocument();
  });

  it('shows manual edit indicator when isManuallyEdited is true', () => {
    render(<EditableField value="修正済み" isManuallyEdited onSave={onSave} />);
    expect(screen.getByTitle('手動修正済み')).toBeInTheDocument();
  });

  it('does not show manual edit indicator when isManuallyEdited is false', () => {
    render(<EditableField value="未修正" onSave={onSave} />);
    expect(screen.queryByTitle('手動修正済み')).not.toBeInTheDocument();
  });

  /* ---------------------------------------------------------------- */
  /*  Entering edit mode                                               */
  /* ---------------------------------------------------------------- */
  it('enters edit mode when edit button is clicked', async () => {
    render(<EditableField value="元の値" onSave={onSave} />);
    fireEvent.click(screen.getByRole('button', { name: /編集/ }));

    const input = screen.getByRole('textbox', { name: 'フィールド編集' });
    expect(input).toBeInTheDocument();
    expect(input).toHaveValue('元の値');
  });

  it('shows save and cancel buttons in edit mode', () => {
    render(<EditableField value="値" onSave={onSave} />);
    fireEvent.click(screen.getByRole('button', { name: /編集/ }));

    expect(screen.getByRole('button', { name: '保存' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'キャンセル' })).toBeInTheDocument();
  });

  /* ---------------------------------------------------------------- */
  /*  Saving                                                           */
  /* ---------------------------------------------------------------- */
  it('calls onSave with the new value when save is clicked', async () => {
    render(<EditableField value="旧値" onSave={onSave} />);
    fireEvent.click(screen.getByRole('button', { name: /編集/ }));

    const input = screen.getByRole('textbox', { name: 'フィールド編集' });
    fireEvent.change(input, { target: { value: '新値' } });
    fireEvent.click(screen.getByRole('button', { name: '保存' }));

    await waitFor(() => {
      expect(onSave).toHaveBeenCalledWith('新値');
    });
  });

  it('exits edit mode after successful save', async () => {
    render(<EditableField value="旧値" onSave={onSave} />);
    fireEvent.click(screen.getByRole('button', { name: /編集/ }));

    const input = screen.getByRole('textbox', { name: 'フィールド編集' });
    fireEvent.change(input, { target: { value: '新値' } });
    fireEvent.click(screen.getByRole('button', { name: '保存' }));

    await waitFor(() => {
      expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
    });
  });

  it('saves on Enter key press', async () => {
    render(<EditableField value="値" onSave={onSave} />);
    fireEvent.click(screen.getByRole('button', { name: /編集/ }));

    const input = screen.getByRole('textbox', { name: 'フィールド編集' });
    fireEvent.change(input, { target: { value: '更新値' } });
    fireEvent.keyDown(input, { key: 'Enter' });

    await waitFor(() => {
      expect(onSave).toHaveBeenCalledWith('更新値');
    });
  });

  /* ---------------------------------------------------------------- */
  /*  Cancelling                                                       */
  /* ---------------------------------------------------------------- */
  it('cancels editing when cancel button is clicked', () => {
    render(<EditableField value="元の値" onSave={onSave} />);
    fireEvent.click(screen.getByRole('button', { name: /編集/ }));

    fireEvent.click(screen.getByRole('button', { name: 'キャンセル' }));

    expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
    expect(screen.getByText('元の値')).toBeInTheDocument();
    expect(onSave).not.toHaveBeenCalled();
  });

  it('cancels editing on Escape key press', () => {
    render(<EditableField value="元の値" onSave={onSave} />);
    fireEvent.click(screen.getByRole('button', { name: /編集/ }));

    const input = screen.getByRole('textbox', { name: 'フィールド編集' });
    fireEvent.keyDown(input, { key: 'Escape' });

    expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
    expect(onSave).not.toHaveBeenCalled();
  });

  /* ---------------------------------------------------------------- */
  /*  Validation – number field type                                   */
  /* ---------------------------------------------------------------- */
  it('shows validation error for non-numeric input in number field', async () => {
    render(<EditableField value="100" fieldType="number" onSave={onSave} />);
    fireEvent.click(screen.getByRole('button', { name: /編集/ }));

    const input = screen.getByRole('textbox', { name: 'フィールド編集' });
    fireEvent.change(input, { target: { value: 'abc' } });
    fireEvent.click(screen.getByRole('button', { name: '保存' }));

    await waitFor(() => {
      expect(screen.getByText('数値を入力してください')).toBeInTheDocument();
    });
    expect(onSave).not.toHaveBeenCalled();
  });

  it('allows empty value for number field', async () => {
    render(<EditableField value="100" fieldType="number" onSave={onSave} />);
    fireEvent.click(screen.getByRole('button', { name: /編集/ }));

    const input = screen.getByRole('textbox', { name: 'フィールド編集' });
    fireEvent.change(input, { target: { value: '' } });
    fireEvent.click(screen.getByRole('button', { name: '保存' }));

    await waitFor(() => {
      expect(onSave).toHaveBeenCalledWith('');
    });
  });

  it('accepts valid numeric input for number field', async () => {
    render(<EditableField value="100" fieldType="number" onSave={onSave} />);
    fireEvent.click(screen.getByRole('button', { name: /編集/ }));

    const input = screen.getByRole('textbox', { name: 'フィールド編集' });
    fireEvent.change(input, { target: { value: '250' } });
    fireEvent.click(screen.getByRole('button', { name: '保存' }));

    await waitFor(() => {
      expect(onSave).toHaveBeenCalledWith('250');
    });
  });

  /* ---------------------------------------------------------------- */
  /*  Validation – currency field type                                 */
  /* ---------------------------------------------------------------- */
  it('shows validation error for negative currency value', async () => {
    render(<EditableField value="1000" fieldType="currency" onSave={onSave} />);
    fireEvent.click(screen.getByRole('button', { name: /編集/ }));

    const input = screen.getByRole('textbox', { name: 'フィールド編集' });
    fireEvent.change(input, { target: { value: '-500' } });
    fireEvent.click(screen.getByRole('button', { name: '保存' }));

    await waitFor(() => {
      expect(screen.getByText('0以上の値を入力してください')).toBeInTheDocument();
    });
    expect(onSave).not.toHaveBeenCalled();
  });

  it('accepts comma-separated numbers for currency field', async () => {
    render(<EditableField value="1000" fieldType="currency" onSave={onSave} />);
    fireEvent.click(screen.getByRole('button', { name: /編集/ }));

    const input = screen.getByRole('textbox', { name: 'フィールド編集' });
    fireEvent.change(input, { target: { value: '1,500' } });
    fireEvent.click(screen.getByRole('button', { name: '保存' }));

    await waitFor(() => {
      expect(onSave).toHaveBeenCalledWith('1,500');
    });
  });

  /* ---------------------------------------------------------------- */
  /*  Error handling                                                   */
  /* ---------------------------------------------------------------- */
  it('displays error message when onSave rejects', async () => {
    const failingSave = vi.fn().mockRejectedValue(new Error('サーバーエラー'));
    render(<EditableField value="値" onSave={failingSave} />);
    fireEvent.click(screen.getByRole('button', { name: /編集/ }));

    fireEvent.click(screen.getByRole('button', { name: '保存' }));

    await waitFor(() => {
      expect(screen.getByText('サーバーエラー')).toBeInTheDocument();
    });
    // Should remain in edit mode
    expect(screen.getByRole('textbox', { name: 'フィールド編集' })).toBeInTheDocument();
  });

  it('displays generic error when onSave throws non-Error', async () => {
    const failingSave = vi.fn().mockRejectedValue('unknown');
    render(<EditableField value="値" onSave={failingSave} />);
    fireEvent.click(screen.getByRole('button', { name: /編集/ }));

    fireEvent.click(screen.getByRole('button', { name: '保存' }));

    await waitFor(() => {
      expect(screen.getByText('保存に失敗しました')).toBeInTheDocument();
    });
  });
});
