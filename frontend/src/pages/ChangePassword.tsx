import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import api from '../services/api';
import { Card } from '../components/ui/Card/Card';
import { Button } from '../components/ui/Button/Button';
import { AxiosError } from 'axios';
import './Login.css';

const ChangePassword: React.FC = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const isInitialSetup = user?.must_change_password ?? false;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!currentPassword) {
      setError('現在のパスワードを入力してください');
      return;
    }
    if (!newPassword || !confirmPassword) {
      setError('新しいパスワードを入力してください');
      return;
    }
    if (newPassword !== confirmPassword) {
      setError('新しいパスワードが一致しません');
      return;
    }

    setIsSubmitting(true);
    try {
      await api.post('/api/auth/change-password', {
        current_password: currentPassword,
        new_password: newPassword,
      });
      // Password changed — force re-login
      await logout();
      navigate('/login', { replace: true });
    } catch (err) {
      if (err instanceof AxiosError) {
        if (err.response?.status === 401) {
          setError('現在のパスワードが正しくありません');
        } else if (err.response?.status === 422) {
          const detail = err.response.data?.detail;
          setError(Array.isArray(detail) ? detail.join('\n') : detail || 'パスワードポリシーを満たしていません');
        } else {
          setError('パスワード変更に失敗しました');
        }
      } else {
        setError('パスワード変更に失敗しました');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="login-page">
      <Card padding="lg" className="login-page__card">
        <h1 className="login-page__title">
          {isInitialSetup ? '初期パスワード設定' : 'パスワード変更'}
        </h1>
        <p className="login-page__subtitle">
          {isInitialSetup
            ? 'セキュリティのため、初回ログイン時にパスワードを変更してください'
            : '新しいパスワードを設定してください'}
        </p>

        <form onSubmit={handleSubmit} className="login-page__form" noValidate>
          {error && (
            <div className="login-page__error" role="alert">
              {error}
            </div>
          )}

          <div className="input-field">
            <label className="input-field__label">
              {isInitialSetup ? '現在のパスワード（自動生成されたパスワード）' : '現在のパスワード'}
            </label>
            <input
              className="input-field__input"
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              placeholder={isInitialSetup ? 'ログに表示されたパスワードを入力' : '現在のパスワードを入力'}
              autoComplete="current-password"
            />
          </div>

          <div className="input-field">
            <label className="input-field__label">新しいパスワード</label>
            <input
              className="input-field__input"
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              placeholder="8文字以上、英大文字・小文字・数字を含む"
              autoComplete="new-password"
            />
          </div>

          <div className="input-field">
            <label className="input-field__label">新しいパスワード（確認）</label>
            <input
              className="input-field__input"
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="新しいパスワードを再入力"
              autoComplete="new-password"
            />
          </div>

          <Button
            variant="primary"
            size="md"
            type="submit"
            loading={isSubmitting}
            disabled={isSubmitting}
          >
            パスワードを変更
          </Button>
        </form>
      </Card>
    </div>
  );
};

export default ChangePassword;
