import React, { useState, useId } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Card } from '../components/ui/Card/Card';
import { Button } from '../components/ui/Button/Button';
import { Input } from '../components/ui/Input/Input';
import { AxiosError } from 'axios';
import './Login.css';

const Login: React.FC = () => {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const passwordId = useId();
  const passwordErrorId = `${passwordId}-error`;

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const from = (location.state as { from?: string })?.from || '/';

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!username.trim() || !password) {
      setError('ユーザ名とパスワードを入力してください');
      return;
    }

    setIsSubmitting(true);
    try {
      await login(username, password);
      // AuthContext now has user info — ProtectedRoute will handle must_change_password redirect
      navigate(from, { replace: true });
    } catch (err) {
      if (err instanceof AxiosError) {
        if (err.response?.status === 429) {
          const retryAfter = err.response.data?.retry_after;
          setError(
            retryAfter
              ? `ログイン試行回数の上限に達しました。${Math.ceil(retryAfter)}秒後に再試行してください`
              : 'ログイン試行回数の上限に達しました。しばらくしてから再試行してください'
          );
        } else if (err.response?.status === 401) {
          setError('ユーザ名またはパスワードが正しくありません');
        } else {
          setError('ログインに失敗しました。しばらくしてから再試行してください');
        }
      } else {
        setError('ログインに失敗しました');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="login-page">
      <Card padding="lg" className="login-page__card">
        <h1 className="login-page__title">ログイン</h1>
        <p className="login-page__subtitle">決済条件監視システム</p>

        <form onSubmit={handleSubmit} className="login-page__form" noValidate>
          {error && (
            <div className="login-page__error" role="alert">
              {error}
            </div>
          )}

          <Input
            label="ユーザ名"
            type="text"
            value={username}
            onChange={setUsername}
            placeholder="ユーザ名を入力"
          />

          <div className="input-field">
            <label className="input-field__label" htmlFor={passwordId}>
              パスワード
            </label>
            <input
              id={passwordId}
              className="input-field__input"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="パスワードを入力"
              aria-describedby={error ? passwordErrorId : undefined}
              autoComplete="current-password"
            />
          </div>

          <Button
            variant="primary"
            size="md"
            type="submit"
            loading={isSubmitting}
            disabled={isSubmitting}
          >
            ログイン
          </Button>
        </form>
      </Card>
    </div>
  );
};

export default Login;
