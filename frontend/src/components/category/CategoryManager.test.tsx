import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import CategoryManager from './CategoryManager';
import { TestQueryClientProvider } from '../../test/testQueryClient';
import * as api from '../../services/api';

// Mock the API module
vi.mock('../../services/api', () => ({
  getCategories: vi.fn(),
  createCategory: vi.fn(),
  updateCategory: vi.fn(),
  deleteCategory: vi.fn(),
}));

const renderWithQueryClient = (ui: React.ReactElement) =>
  render(<TestQueryClientProvider>{ui}</TestQueryClientProvider>);

describe('CategoryManager', () => {
  const mockCategories = [
    {
      id: 1,
      name: 'テストカテゴリ1',
      description: 'テスト説明1',
      color: '#FF0000',
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:00:00Z',
    },
    {
      id: 2,
      name: 'テストカテゴリ2',
      description: null,
      color: '#00FF00',
      created_at: '2024-01-02T00:00:00Z',
      updated_at: '2024-01-02T00:00:00Z',
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should display loading state initially', () => {
    vi.mocked(api.getCategories).mockImplementation(() => new Promise(() => {}));
    
    renderWithQueryClient(<CategoryManager />);
    
    // Check for the spinner element
    const spinner = document.querySelector('.animate-spin');
    expect(spinner).toBeInTheDocument();
  });

  it('should display categories after loading', async () => {
    vi.mocked(api.getCategories).mockResolvedValue(mockCategories);
    
    renderWithQueryClient(<CategoryManager />);
    
    await waitFor(() => {
      expect(screen.getByText('テストカテゴリ1')).toBeInTheDocument();
      expect(screen.getByText('テストカテゴリ2')).toBeInTheDocument();
    });
  });

  it('should display empty state when no categories', async () => {
    vi.mocked(api.getCategories).mockResolvedValue([]);
    
    renderWithQueryClient(<CategoryManager />);
    
    await waitFor(() => {
      expect(screen.getByText('カテゴリがありません')).toBeInTheDocument();
    });
  });

  it('should show add form when clicking add button', async () => {
    vi.mocked(api.getCategories).mockResolvedValue(mockCategories);
    
    renderWithQueryClient(<CategoryManager />);
    
    await waitFor(() => {
      expect(screen.getByText('テストカテゴリ1')).toBeInTheDocument();
    });

    const addButton = screen.getByText('新規カテゴリ追加');
    fireEvent.click(addButton);

    expect(screen.getByText('新規カテゴリ')).toBeInTheDocument();
    expect(screen.getByLabelText(/カテゴリ名/)).toBeInTheDocument();
  });

  it('should create a new category', async () => {
    vi.mocked(api.getCategories).mockResolvedValue(mockCategories);
    vi.mocked(api.createCategory).mockResolvedValue({
      id: 3,
      name: '新規カテゴリ',
      description: '新規説明',
      color: '#0000FF',
      created_at: '2024-01-03T00:00:00Z',
      updated_at: '2024-01-03T00:00:00Z',
    });

    renderWithQueryClient(<CategoryManager />);

    await waitFor(() => {
      expect(screen.getByText('テストカテゴリ1')).toBeInTheDocument();
    });

    // Open add form
    fireEvent.click(screen.getByText('新規カテゴリ追加'));

    // Fill form
    const nameInput = screen.getByLabelText(/カテゴリ名/);
    fireEvent.change(nameInput, { target: { value: '新規カテゴリ' } });

    const descriptionInput = screen.getByLabelText(/説明/);
    fireEvent.change(descriptionInput, { target: { value: '新規説明' } });

    // Submit form
    const submitButton = screen.getByText('作成');
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(api.createCategory).toHaveBeenCalledWith({
        name: '新規カテゴリ',
        description: '新規説明',
        color: '#3B82F6',
      });
    });
  });

  it('should show delete confirmation dialog', async () => {
    vi.mocked(api.getCategories).mockResolvedValue(mockCategories);
    
    renderWithQueryClient(<CategoryManager />);
    
    await waitFor(() => {
      expect(screen.getByText('テストカテゴリ1')).toBeInTheDocument();
    });

    const deleteButtons = screen.getAllByText('削除');
    fireEvent.click(deleteButtons[0]);

    expect(screen.getByText('カテゴリの削除')).toBeInTheDocument();
    expect(screen.getByText(/配下のサイト・契約条件は未分類に移動されます/)).toBeInTheDocument();
  });

  it('should delete category after confirmation', async () => {
    vi.mocked(api.getCategories).mockResolvedValue(mockCategories);
    vi.mocked(api.deleteCategory).mockResolvedValue();

    renderWithQueryClient(<CategoryManager />);

    await waitFor(() => {
      expect(screen.getByText('テストカテゴリ1')).toBeInTheDocument();
    });

    // Click delete button
    const deleteButtons = screen.getAllByText('削除');
    fireEvent.click(deleteButtons[0]);

    // Wait for dialog to appear
    await waitFor(() => {
      expect(screen.getByText('カテゴリの削除')).toBeInTheDocument();
    });

    // Confirm deletion - find the button in the dialog
    const dialogButtons = screen.getAllByRole('button');
    const confirmDeleteButton = dialogButtons.find(btn => 
      btn.textContent === '削除' && btn.className.includes('bg-red-600')
    );
    
    if (confirmDeleteButton) {
      fireEvent.click(confirmDeleteButton);
    }

    await waitFor(() => {
      expect(api.deleteCategory).toHaveBeenCalled();
      expect(vi.mocked(api.deleteCategory).mock.calls[0][0]).toBe(1);
    });
  });

  it('should display empty state on load failure', async () => {
    vi.mocked(api.getCategories).mockRejectedValue(new Error('Network error'));
    
    renderWithQueryClient(<CategoryManager />);
    
    await waitFor(() => {
      expect(screen.getByText('カテゴリがありません')).toBeInTheDocument();
    });
  });

  it('should display error on duplicate category name', async () => {
    vi.mocked(api.getCategories).mockResolvedValue(mockCategories);
    vi.mocked(api.createCategory).mockRejectedValue({
      response: { status: 409 },
    });

    renderWithQueryClient(<CategoryManager />);

    await waitFor(() => {
      expect(screen.getByText('テストカテゴリ1')).toBeInTheDocument();
    });

    // Open add form
    fireEvent.click(screen.getByText('新規カテゴリ追加'));

    // Fill form with duplicate name
    const nameInput = screen.getByLabelText(/カテゴリ名/);
    fireEvent.change(nameInput, { target: { value: 'テストカテゴリ1' } });

    // Submit form
    const submitButton = screen.getByText('作成');
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText('同名のカテゴリが既に存在します')).toBeInTheDocument();
    });
  });

  it('should populate form when editing a category', async () => {
    vi.mocked(api.getCategories).mockResolvedValue(mockCategories);
    
    renderWithQueryClient(<CategoryManager />);
    
    await waitFor(() => {
      expect(screen.getByText('テストカテゴリ1')).toBeInTheDocument();
    });

    // Click edit button
    const editButtons = screen.getAllByText('編集');
    fireEvent.click(editButtons[0]);

    // Check form is populated
    expect(screen.getByText('カテゴリ編集')).toBeInTheDocument();
    const nameInput = screen.getByLabelText(/カテゴリ名/) as HTMLInputElement;
    expect(nameInput.value).toBe('テストカテゴリ1');
  });

  it('should call onCategoryChange callback after successful create', async () => {
    const onCategoryChange = vi.fn();
    vi.mocked(api.getCategories).mockResolvedValue(mockCategories);
    vi.mocked(api.createCategory).mockResolvedValue({
      id: 3,
      name: '新規カテゴリ',
      description: '',
      color: '#3B82F6',
      created_at: '2024-01-03T00:00:00Z',
      updated_at: '2024-01-03T00:00:00Z',
    });

    renderWithQueryClient(<CategoryManager onCategoryChange={onCategoryChange} />);

    await waitFor(() => {
      expect(screen.getByText('テストカテゴリ1')).toBeInTheDocument();
    });

    // Open add form and submit
    fireEvent.click(screen.getByText('新規カテゴリ追加'));
    const nameInput = screen.getByLabelText(/カテゴリ名/);
    fireEvent.change(nameInput, { target: { value: '新規カテゴリ' } });
    fireEvent.click(screen.getByText('作成'));

    await waitFor(() => {
      expect(onCategoryChange).toHaveBeenCalled();
    });
  });
});
