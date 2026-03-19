/**
 * Simple authentication guard component.
 *
 * Checks that an API key is configured before rendering children.
 * In a production app this would verify a session/token; here we
 * just ensure the VITE_API_KEY env var (or the dev default) is set.
 */

import { type ReactNode } from 'react';

const API_KEY = import.meta.env.VITE_API_KEY || 'dev-api-key';

interface AuthGuardProps {
  children: ReactNode;
}

const AuthGuard: React.FC<AuthGuardProps> = ({ children }) => {
  if (!API_KEY) {
    return (
      <div style={{ padding: '2rem', textAlign: 'center' }}>
        <h2>認証が必要です</h2>
        <p>
          APIキーが設定されていません。環境変数{' '}
          <code>VITE_API_KEY</code> を設定してください。
        </p>
      </div>
    );
  }

  return <>{children}</>;
};

export default AuthGuard;
