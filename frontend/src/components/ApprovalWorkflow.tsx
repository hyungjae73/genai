import React, { useState } from 'react';
import { approveExtractedData, rejectExtractedData } from '../api/extractedData';

/* ------------------------------------------------------------------ */
/*  ApprovalWorkflow – approve / reject buttons & status display       */
/* ------------------------------------------------------------------ */

export interface ApprovalWorkflowProps {
  /** Extracted payment info record ID */
  extractedDataId: number;
  /** Current status */
  status: 'pending' | 'approved' | 'rejected' | 'failed';
  /** Approver name (shown when already approved/rejected) */
  approvedBy?: string | null;
  /** Approval timestamp */
  approvedAt?: string | null;
  /** Rejection reason (shown when rejected) */
  rejectionReason?: string | null;
  /** Callback after status change */
  onStatusChange?: (newStatus: 'approved' | 'rejected') => void;
}

const ApprovalWorkflow: React.FC<ApprovalWorkflowProps> = ({
  extractedDataId,
  status,
  approvedBy,
  approvedAt,
  rejectionReason,
  onStatusChange,
}) => {
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showRejectForm, setShowRejectForm] = useState(false);
  const [rejectReason, setRejectReason] = useState('');

  const handleApprove = async () => {
    setProcessing(true);
    setError(null);
    try {
      await approveExtractedData(extractedDataId);
      onStatusChange?.('approved');
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : '承認に失敗しました');
    } finally {
      setProcessing(false);
    }
  };

  const handleReject = async () => {
    if (!rejectReason.trim()) {
      setError('却下理由を入力してください');
      return;
    }
    setProcessing(true);
    setError(null);
    try {
      await rejectExtractedData(extractedDataId, rejectReason.trim());
      onStatusChange?.('rejected');
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : '却下に失敗しました');
    } finally {
      setProcessing(false);
    }
  };

  /* ---- Already approved ---- */
  if (status === 'approved') {
    return (
      <div
        className="approval-workflow"
        style={{
          border: '1px solid var(--success-color, #10b981)',
          borderRadius: '8px',
          padding: '0.75rem 1rem',
          marginTop: '1rem',
          backgroundColor: 'rgba(16, 185, 129, 0.05)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem' }}>
          <span style={{ fontSize: '1.1rem' }}>✅</span>
          <span style={{ fontWeight: 600, color: 'var(--success-color, #10b981)' }}>承認済み</span>
        </div>
        {approvedBy && (
          <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary, #6b7280)', margin: '0.15rem 0' }}>
            承認者: {approvedBy}
          </p>
        )}
        {approvedAt && (
          <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary, #6b7280)', margin: '0.15rem 0' }}>
            承認日時: {new Date(approvedAt).toLocaleString('ja-JP')}
          </p>
        )}
      </div>
    );
  }

  /* ---- Already rejected ---- */
  if (status === 'rejected') {
    return (
      <div
        className="approval-workflow"
        style={{
          border: '1px solid var(--danger-color, #ef4444)',
          borderRadius: '8px',
          padding: '0.75rem 1rem',
          marginTop: '1rem',
          backgroundColor: 'rgba(239, 68, 68, 0.05)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem' }}>
          <span style={{ fontSize: '1.1rem' }}>❌</span>
          <span style={{ fontWeight: 600, color: 'var(--danger-color, #ef4444)' }}>却下</span>
        </div>
        {approvedBy && (
          <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary, #6b7280)', margin: '0.15rem 0' }}>
            却下者: {approvedBy}
          </p>
        )}
        {approvedAt && (
          <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary, #6b7280)', margin: '0.15rem 0' }}>
            却下日時: {new Date(approvedAt).toLocaleString('ja-JP')}
          </p>
        )}
        {rejectionReason && (
          <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary, #6b7280)', margin: '0.15rem 0' }}>
            理由: {rejectionReason}
          </p>
        )}
      </div>
    );
  }

  /* ---- Pending: show approve/reject buttons ---- */
  return (
    <div
      className="approval-workflow"
      style={{
        border: '1px solid var(--border-color, #e5e7eb)',
        borderRadius: '8px',
        padding: '0.75rem 1rem',
        marginTop: '1rem',
      }}
    >
      <p style={{ fontWeight: 600, fontSize: '0.9rem', marginBottom: '0.5rem' }}>承認ワークフロー</p>

      {!showRejectForm ? (
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          <button
            type="button"
            onClick={handleApprove}
            disabled={processing}
            style={{
              padding: '0.4rem 1rem',
              fontSize: '0.85rem',
              fontWeight: 600,
              backgroundColor: 'var(--success-color, #10b981)',
              color: '#fff',
              border: 'none',
              borderRadius: '6px',
              cursor: processing ? 'wait' : 'pointer',
              opacity: processing ? 0.7 : 1,
            }}
          >
            {processing ? '処理中...' : '✓ 承認'}
          </button>
          <button
            type="button"
            onClick={() => { setShowRejectForm(true); setError(null); }}
            disabled={processing}
            style={{
              padding: '0.4rem 1rem',
              fontSize: '0.85rem',
              fontWeight: 600,
              backgroundColor: 'var(--danger-color, #ef4444)',
              color: '#fff',
              border: 'none',
              borderRadius: '6px',
              cursor: processing ? 'wait' : 'pointer',
              opacity: processing ? 0.7 : 1,
            }}
          >
            ✕ 却下
          </button>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
          <label htmlFor="reject-reason" style={{ fontSize: '0.8rem', fontWeight: 500 }}>
            却下理由 <span style={{ color: 'var(--danger-color, #ef4444)' }}>*</span>
          </label>
          <textarea
            id="reject-reason"
            value={rejectReason}
            onChange={(e) => { setRejectReason(e.target.value); setError(null); }}
            placeholder="却下理由を入力してください（必須）"
            rows={3}
            disabled={processing}
            style={{
              padding: '0.4rem',
              fontSize: '0.85rem',
              border: '1px solid var(--border-color, #e5e7eb)',
              borderRadius: '6px',
              resize: 'vertical',
            }}
          />
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button
              type="button"
              onClick={handleReject}
              disabled={processing || !rejectReason.trim()}
              style={{
                padding: '0.35rem 0.8rem',
                fontSize: '0.8rem',
                fontWeight: 600,
                backgroundColor: 'var(--danger-color, #ef4444)',
                color: '#fff',
                border: 'none',
                borderRadius: '6px',
                cursor: processing || !rejectReason.trim() ? 'not-allowed' : 'pointer',
                opacity: processing || !rejectReason.trim() ? 0.6 : 1,
              }}
            >
              {processing ? '処理中...' : '却下を確定'}
            </button>
            <button
              type="button"
              onClick={() => { setShowRejectForm(false); setRejectReason(''); setError(null); }}
              disabled={processing}
              style={{
                padding: '0.35rem 0.8rem',
                fontSize: '0.8rem',
                backgroundColor: 'transparent',
                border: '1px solid var(--border-color, #e5e7eb)',
                borderRadius: '6px',
                cursor: 'pointer',
                color: 'var(--text-secondary, #6b7280)',
              }}
            >
              キャンセル
            </button>
          </div>
        </div>
      )}

      {error && (
        <p style={{ color: 'var(--danger-color, #ef4444)', fontSize: '0.8rem', marginTop: '0.4rem' }}>
          {error}
        </p>
      )}
    </div>
  );
};

export default ApprovalWorkflow;
