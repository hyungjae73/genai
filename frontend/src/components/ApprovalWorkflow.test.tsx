/**
 * Unit tests for ApprovalWorkflow component.
 *
 * Tests cover:
 * - Approve button sets status to "approved"
 * - Reject button sets status to "rejected"
 * - Rejection requires a reason comment (validation)
 * - Approved/rejected status display
 * - Error handling on API failure
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import ApprovalWorkflow from './ApprovalWorkflow';

/* ---- Mock the API module ---- */
vi.mock('../api/extractedData', () => ({
  approveExtractedData: vi.fn(),
  rejectExtractedData: vi.fn(),
}));

import { approveExtractedData, rejectExtractedData } from '../api/extractedData';

const mockApprove = vi.mocked(approveExtractedData);
const mockReject = vi.mocked(rejectExtractedData);

describe('ApprovalWorkflow', () => {
  let onStatusChange: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.clearAllMocks();
    mockApprove.mockResolvedValue(undefined);
    mockReject.mockResolvedValue(undefined);
    onStatusChange = vi.fn();
  });

  /* ---------------------------------------------------------------- */
  /*  Pending state – buttons visible                                  */
  /* ---------------------------------------------------------------- */
  it('renders approve and reject buttons when status is pending', () => {
    render(
      <ApprovalWorkflow extractedDataId={1} status="pending" onStatusChange={onStatusChange} />,
    );
    expect(screen.getByRole('button', { name: /承認/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /却下/ })).toBeInTheDocument();
  });

  it('shows workflow title when pending', () => {
    render(<ApprovalWorkflow extractedDataId={1} status="pending" />);
    expect(screen.getByText('承認ワークフロー')).toBeInTheDocument();
  });

  /* ---------------------------------------------------------------- */
  /*  Approve flow                                                     */
  /* ---------------------------------------------------------------- */
  it('calls approveExtractedData API on approve click', async () => {
    render(
      <ApprovalWorkflow extractedDataId={42} status="pending" onStatusChange={onStatusChange} />,
    );
    fireEvent.click(screen.getByRole('button', { name: /承認/ }));

    await waitFor(() => {
      expect(mockApprove).toHaveBeenCalledWith(42);
    });
  });

  it('calls onStatusChange with "approved" after successful approval', async () => {
    render(
      <ApprovalWorkflow extractedDataId={1} status="pending" onStatusChange={onStatusChange} />,
    );
    fireEvent.click(screen.getByRole('button', { name: /承認/ }));

    await waitFor(() => {
      expect(onStatusChange).toHaveBeenCalledWith('approved');
    });
  });

  it('shows error message when approval API fails', async () => {
    mockApprove.mockRejectedValue(new Error('ネットワークエラー'));
    render(
      <ApprovalWorkflow extractedDataId={1} status="pending" onStatusChange={onStatusChange} />,
    );
    fireEvent.click(screen.getByRole('button', { name: /承認/ }));

    await waitFor(() => {
      expect(screen.getByText('ネットワークエラー')).toBeInTheDocument();
    });
    expect(onStatusChange).not.toHaveBeenCalled();
  });

  it('shows generic error when approval throws non-Error', async () => {
    mockApprove.mockRejectedValue('unknown');
    render(
      <ApprovalWorkflow extractedDataId={1} status="pending" onStatusChange={onStatusChange} />,
    );
    fireEvent.click(screen.getByRole('button', { name: /承認/ }));

    await waitFor(() => {
      expect(screen.getByText('承認に失敗しました')).toBeInTheDocument();
    });
  });

  /* ---------------------------------------------------------------- */
  /*  Reject flow                                                      */
  /* ---------------------------------------------------------------- */
  it('shows rejection reason form when reject button is clicked', () => {
    render(<ApprovalWorkflow extractedDataId={1} status="pending" />);
    fireEvent.click(screen.getByRole('button', { name: /却下/ }));

    expect(screen.getByLabelText(/却下理由/)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/却下理由を入力してください/)).toBeInTheDocument();
  });

  it('requires rejection reason – shows error when empty', async () => {
    render(
      <ApprovalWorkflow extractedDataId={1} status="pending" onStatusChange={onStatusChange} />,
    );
    fireEvent.click(screen.getByRole('button', { name: /却下/ }));

    // The confirm button should be disabled when reason is empty
    const confirmBtn = screen.getByRole('button', { name: /却下を確定/ });
    expect(confirmBtn).toBeDisabled();
    expect(mockReject).not.toHaveBeenCalled();
  });

  it('calls rejectExtractedData API with reason on confirm', async () => {
    render(
      <ApprovalWorkflow extractedDataId={7} status="pending" onStatusChange={onStatusChange} />,
    );
    fireEvent.click(screen.getByRole('button', { name: /却下/ }));

    const textarea = screen.getByPlaceholderText(/却下理由を入力してください/);
    fireEvent.change(textarea, { target: { value: 'データが不正確です' } });
    fireEvent.click(screen.getByRole('button', { name: /却下を確定/ }));

    await waitFor(() => {
      expect(mockReject).toHaveBeenCalledWith(7, 'データが不正確です');
    });
  });

  it('calls onStatusChange with "rejected" after successful rejection', async () => {
    render(
      <ApprovalWorkflow extractedDataId={1} status="pending" onStatusChange={onStatusChange} />,
    );
    fireEvent.click(screen.getByRole('button', { name: /却下/ }));

    const textarea = screen.getByPlaceholderText(/却下理由を入力してください/);
    fireEvent.change(textarea, { target: { value: '理由あり' } });
    fireEvent.click(screen.getByRole('button', { name: /却下を確定/ }));

    await waitFor(() => {
      expect(onStatusChange).toHaveBeenCalledWith('rejected');
    });
  });

  it('shows error message when rejection API fails', async () => {
    mockReject.mockRejectedValue(new Error('サーバーエラー'));
    render(
      <ApprovalWorkflow extractedDataId={1} status="pending" onStatusChange={onStatusChange} />,
    );
    fireEvent.click(screen.getByRole('button', { name: /却下/ }));

    const textarea = screen.getByPlaceholderText(/却下理由を入力してください/);
    fireEvent.change(textarea, { target: { value: '理由' } });
    fireEvent.click(screen.getByRole('button', { name: /却下を確定/ }));

    await waitFor(() => {
      expect(screen.getByText('サーバーエラー')).toBeInTheDocument();
    });
    expect(onStatusChange).not.toHaveBeenCalled();
  });

  it('cancels rejection form and returns to buttons', () => {
    render(<ApprovalWorkflow extractedDataId={1} status="pending" />);
    fireEvent.click(screen.getByRole('button', { name: /却下/ }));
    expect(screen.getByPlaceholderText(/却下理由を入力してください/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'キャンセル' }));
    expect(screen.queryByPlaceholderText(/却下理由を入力してください/)).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /承認/ })).toBeInTheDocument();
  });

  it('trims whitespace from rejection reason', async () => {
    render(
      <ApprovalWorkflow extractedDataId={1} status="pending" onStatusChange={onStatusChange} />,
    );
    fireEvent.click(screen.getByRole('button', { name: /却下/ }));

    const textarea = screen.getByPlaceholderText(/却下理由を入力してください/);
    fireEvent.change(textarea, { target: { value: '  理由テスト  ' } });
    fireEvent.click(screen.getByRole('button', { name: /却下を確定/ }));

    await waitFor(() => {
      expect(mockReject).toHaveBeenCalledWith(1, '理由テスト');
    });
  });

  /* ---------------------------------------------------------------- */
  /*  Approved status display                                          */
  /* ---------------------------------------------------------------- */
  it('displays approved status with approver info', () => {
    render(
      <ApprovalWorkflow
        extractedDataId={1}
        status="approved"
        approvedBy="admin_user"
        approvedAt="2024-06-15T10:00:00Z"
      />,
    );
    expect(screen.getByText('承認済み')).toBeInTheDocument();
    expect(screen.getByText(/admin_user/)).toBeInTheDocument();
  });

  it('does not show approve/reject buttons when approved', () => {
    render(<ApprovalWorkflow extractedDataId={1} status="approved" />);
    expect(screen.queryByRole('button', { name: /承認/ })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /却下/ })).not.toBeInTheDocument();
  });

  /* ---------------------------------------------------------------- */
  /*  Rejected status display                                          */
  /* ---------------------------------------------------------------- */
  it('displays rejected status with reason', () => {
    render(
      <ApprovalWorkflow
        extractedDataId={1}
        status="rejected"
        approvedBy="reviewer"
        rejectionReason="データ不正"
      />,
    );
    expect(screen.getByText('却下')).toBeInTheDocument();
    expect(screen.getByText(/reviewer/)).toBeInTheDocument();
    expect(screen.getByText(/データ不正/)).toBeInTheDocument();
  });

  it('does not show approve/reject buttons when rejected', () => {
    render(<ApprovalWorkflow extractedDataId={1} status="rejected" />);
    expect(screen.queryByRole('button', { name: /承認/ })).not.toBeInTheDocument();
  });
});
