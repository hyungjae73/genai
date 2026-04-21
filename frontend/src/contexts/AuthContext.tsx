import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import api, { setAuthInterceptors } from '../services/api';

export interface AuthUser {
  id: number;
  username: string;
  role: string;
  must_change_password: boolean;
}

export interface AuthState {
  user: AuthUser | null;
  accessToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
}

export interface AuthContextType extends AuthState {
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshToken: () => Promise<string | null>;
  hasRole: (...roles: string[]) => boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const refreshPromiseRef = useRef<Promise<string | null> | null>(null);

  const isAuthenticated = !!user && !!accessToken;

  const clearAuth = useCallback(() => {
    setUser(null);
    setAccessToken(null);
  }, []);

  const refreshTokenFn = useCallback(async (): Promise<string | null> => {
    // Deduplicate concurrent refresh calls
    if (refreshPromiseRef.current) {
      return refreshPromiseRef.current;
    }

    const promise = (async () => {
      try {
        const response = await api.post('/api/auth/refresh', {}, { withCredentials: true });
        const { access_token } = response.data;
        const meResponse = await api.get('/api/auth/me', {
          headers: { Authorization: `Bearer ${access_token}` },
        });
        setAccessToken(access_token);
        setUser(meResponse.data);
        return access_token as string;
      } catch {
        clearAuth();
        return null;
      } finally {
        refreshPromiseRef.current = null;
      }
    })();

    refreshPromiseRef.current = promise;
    return promise;
  }, [clearAuth]);

  const login = useCallback(async (username: string, password: string): Promise<void> => {
    const response = await api.post('/api/auth/login', { username, password }, { withCredentials: true });
    const { access_token } = response.data;
    const meResponse = await api.get('/api/auth/me', {
      headers: { Authorization: `Bearer ${access_token}` },
    });
    setAccessToken(access_token);
    setUser(meResponse.data);
  }, []);

  const logout = useCallback(async (): Promise<void> => {
    try {
      await api.post('/api/auth/logout', {}, {
        headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {},
        withCredentials: true,
      });
    } catch {
      // Ignore logout errors
    } finally {
      clearAuth();
    }
  }, [accessToken, clearAuth]);

  const hasRole = useCallback((...roles: string[]): boolean => {
    if (!user) return false;
    return roles.includes(user.role);
  }, [user]);

  // Wire up axios interceptors with current auth state
  const accessTokenRef = useRef(accessToken);
  accessTokenRef.current = accessToken;

  useEffect(() => {
    setAuthInterceptors(
      () => accessTokenRef.current,
      refreshTokenFn,
      clearAuth,
    );
  }, [refreshTokenFn, clearAuth]);

  // On mount: try to restore session via refresh
  useEffect(() => {
    const restoreSession = async () => {
      try {
        await refreshTokenFn();
      } catch {
        // No valid session
      } finally {
        setIsLoading(false);
      }
    };
    restoreSession();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const value: AuthContextType = {
    user,
    accessToken,
    isAuthenticated,
    isLoading,
    login,
    logout,
    refreshToken: refreshTokenFn,
    hasRole,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export default AuthContext;
