import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import FieldSchemaManager from './FieldSchemaManager';
import * as api from '../../services/api';

vi.mock('../../services/api');

describe('FieldSchemaManager', () => {
  const mockCategoryId = 1;
  const mockSchemas: api.FieldSchema[] = [
    {
      id: 1,
      category_id: mockCategoryId,
      field_name: 'price',
      field_type: 'currency',
      is_required: true,
      validation_rules: { min: 0, currency_code: 'JPY' },
      display_order: 0,
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:00:00Z',
    },
    {
      id: 2,
      category_id: mockCategoryId,
      field_name: 'description',
      field_type: 'text',
      is_required: false,
      validation_rules: null,
      display_order: 1,
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:00:00Z',
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders loading state initially', () => {
    vi.mocked(api.getFieldSchemas).mockImplementation(() => new Promise(() => {}));
    
    render(<FieldSchemaManager categoryId={mockCategoryId} />);
    
    // Check for the spinner element instead of role
    const spinner = document.querySelector('.animate-spin');
    expect(spinner).toBeInTheDocument();
  });

  it('renders field schemas list after loading', async () => {
    vi.mocked(api.getFieldSchemas).mockResolvedValue(mockSchemas);
    
    render(<FieldSchemaManager categoryId={mockCategoryId} />);
    
    await waitFor(() => {
      expect(screen.getByText('price')).toBeInTheDocument();
      expect(screen.getByText('description')).toBeInTheDocument();
    });
  });

  it('displays empty state when no schemas exist', async () => {
    vi.mocked(api.getFieldSchemas).mockResolvedValue([]);
    
    render(<FieldSchemaManager categoryId={mockCategoryId} />);
    
    await waitFor(() => {
      expect(screen.getByText('フィールドスキーマがありません')).toBeInTheDocument();
    });
  });

  it('shows add form when add button is clicked', async () => {
    vi.mocked(api.getFieldSchemas).mockResolvedValue(mockSchemas);
    const user = userEvent.setup();
    
    render(<FieldSchemaManager categoryId={mockCategoryId} />);
    
    await waitFor(() => {
      expect(screen.getByText('price')).toBeInTheDocument();
    });
    
    const addButton = screen.getByText('新規フィールド追加');
    await user.click(addButton);
    
    expect(screen.getByText('新規フィールド')).toBeInTheDocument();
    expect(screen.getByLabelText(/フィールド名/)).toBeInTheDocument();
  });

  it('displays required badge for required fields', async () => {
    vi.mocked(api.getFieldSchemas).mockResolvedValue(mockSchemas);
    
    render(<FieldSchemaManager categoryId={mockCategoryId} />);
    
    await waitFor(() => {
      const requiredBadges = screen.getAllByText('必須');
      expect(requiredBadges.length).toBeGreaterThan(0);
    });
  });

  it('displays optional badge for optional fields', async () => {
    vi.mocked(api.getFieldSchemas).mockResolvedValue(mockSchemas);
    
    render(<FieldSchemaManager categoryId={mockCategoryId} />);
    
    await waitFor(() => {
      const optionalBadges = screen.getAllByText('任意');
      expect(optionalBadges.length).toBeGreaterThan(0);
    });
  });

  it('shows validation rules when present', async () => {
    vi.mocked(api.getFieldSchemas).mockResolvedValue(mockSchemas);
    
    render(<FieldSchemaManager categoryId={mockCategoryId} />);
    
    await waitFor(() => {
      expect(screen.getByText(/"min"/)).toBeInTheDocument();
      expect(screen.getByText(/"currency_code"/)).toBeInTheDocument();
    });
  });

  it('displays error message when loading fails', async () => {
    vi.mocked(api.getFieldSchemas).mockRejectedValue(new Error('Network error'));
    
    render(<FieldSchemaManager categoryId={mockCategoryId} />);
    
    await waitFor(() => {
      expect(screen.getByText('フィールドスキーマの読み込みに失敗しました')).toBeInTheDocument();
    });
  });

  it('shows edit form when edit button is clicked', async () => {
    vi.mocked(api.getFieldSchemas).mockResolvedValue(mockSchemas);
    const user = userEvent.setup();
    
    render(<FieldSchemaManager categoryId={mockCategoryId} />);
    
    await waitFor(() => {
      expect(screen.getByText('price')).toBeInTheDocument();
    });
    
    const editButtons = screen.getAllByText('編集');
    await user.click(editButtons[0]);
    
    expect(screen.getByText('フィールド編集')).toBeInTheDocument();
    expect(screen.getByDisplayValue('price')).toBeInTheDocument();
  });

  it('shows delete confirmation dialog when delete button is clicked', async () => {
    vi.mocked(api.getFieldSchemas).mockResolvedValue(mockSchemas);
    const user = userEvent.setup();
    
    render(<FieldSchemaManager categoryId={mockCategoryId} />);
    
    await waitFor(() => {
      expect(screen.getByText('price')).toBeInTheDocument();
    });
    
    const deleteButtons = screen.getAllByText('削除');
    await user.click(deleteButtons[0]);
    
    expect(screen.getByText('フィールドスキーマの削除')).toBeInTheDocument();
    expect(screen.getByText('このフィールドスキーマを削除してもよろしいですか？')).toBeInTheDocument();
  });

  it('renders all field type options', async () => {
    vi.mocked(api.getFieldSchemas).mockResolvedValue(mockSchemas);
    const user = userEvent.setup();
    
    render(<FieldSchemaManager categoryId={mockCategoryId} />);
    
    await waitFor(() => {
      expect(screen.getByText('price')).toBeInTheDocument();
    });
    
    const addButton = screen.getByText('新規フィールド追加');
    await user.click(addButton);
    
    const fieldTypeSelect = screen.getByLabelText(/フィールド型/);
    expect(fieldTypeSelect).toBeInTheDocument();
    
    // Check that all field types are available
    const options = (fieldTypeSelect as HTMLSelectElement).options;
    const optionValues = Array.from(options).map(opt => opt.value);
    
    expect(optionValues).toContain('text');
    expect(optionValues).toContain('number');
    expect(optionValues).toContain('currency');
    expect(optionValues).toContain('percentage');
    expect(optionValues).toContain('date');
    expect(optionValues).toContain('boolean');
    expect(optionValues).toContain('list');
  });
});
