import { useState } from 'react';
import { useUsers, useCreateUser, useUpdateUser, useDeactivateUser, useResetUserPassword } from '../hooks/queries/useUsers';
import { Card } from '../components/ui/Card/Card';
import { Badge } from '../components/ui/Badge/Badge';
import { Button } from '../components/ui/Button/Button';
import { Modal } from '../components/ui/Modal/Modal';
import { Input } from '../components/ui/Input/Input';
import { Select } from '../components/ui/Select/Select';
import './Users.css';

interface User {
  id: number;
  username: string;
  email: string;
  role: string;
  is_active: boolean;
  must_change_password: boolean;
  created_at: string;
  updated_at: string;
}

const roleOptions = [
  { value: 'admin', label: '管理者 (admin)' },
  { value: 'reviewer', label: '審査者 (reviewer)' },
  { value: 'viewer', label: '閲覧者 (viewer)' },
];

const roleBadgeVariant: Record<string, 'danger' | 'warning' | 'info'> = {
  admin: 'danger',
  reviewer: 'warning',
  viewer: 'info',
};

const Users = () => {
  const { data: users = [], isLoading: loading, error: queryError } = useUsers();
  const error = queryError ? 'ユーザ一覧の取得に失敗しました' : null;

  const createUserMutation = useCreateUser();
  const updateUserMutation = useUpdateUser();
  const deactivateUserMutation = useDeactivateUser();
  const resetPasswordMutation = useResetUserPassword();

  // Create modal
  const [showCreate, setShowCreate] = useState(false);
  const [createForm, setCreateForm] = useState({ username: '', email: '', password: '', role: 'viewer' });
  const [createError, setCreateError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  // Edit modal
  const [editUser, setEditUser] = useState<User | null>(null);
  const [editForm, setEditForm] = useState({ email: '', role: '' });
  const [editError, setEditError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);

  // Reset password modal
  const [resetUser, setResetUser] = useState<User | null>(null);
  const [resetPassword, setResetPassword] = useState('');
  const [resetError, setResetError] = useState<string | null>(null);
  const [resetting, setResetting] = useState(false);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreateError(null);
    setCreating(true);
    try {
      await createUserMutation.mutateAsync(createForm);
      setShowCreate(false);
      setCreateForm({ username: '', email: '', password: '', role: 'viewer' });
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      setCreateError(Array.isArray(detail) ? detail.join('\n') : detail || 'エラーが発生しました');
    } finally {
      setCreating(false);
    }
  };

  const handleEdit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editUser) return;
    setEditError(null);
    setEditing(true);
    try {
      await updateUserMutation.mutateAsync({
        id: editUser.id,
        data: {
          email: editForm.email || undefined,
          role: editForm.role || undefined,
        },
      });
      setEditUser(null);
    } catch (err: any) {
      setEditError(err.response?.data?.detail || 'エラーが発生しました');
    } finally {
      setEditing(false);
    }
  };

  const handleDeactivate = async (user: User) => {
    if (!confirm(`「${user.username}」を無効化してもよろしいですか？`)) return;
    try {
      await deactivateUserMutation.mutateAsync(user.id);
    } catch (err: any) {
      alert(err.response?.data?.detail || '無効化に失敗しました');
    }
  };

  const handleResetPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!resetUser) return;
    setResetError(null);
    setResetting(true);
    try {
      await resetPasswordMutation.mutateAsync({ id: resetUser.id, new_password: resetPassword });
      setResetUser(null);
      setResetPassword('');
      alert('パスワードをリセットしました。次回ログイン時にパスワード変更が求められます。');
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      setResetError(Array.isArray(detail) ? detail.join('\n') : detail || 'エラーが発生しました');
    } finally {
      setResetting(false);
    }
  };

  if (loading) return <div className="loading">読み込み中...</div>;
  if (error) return <div className="error">{error}</div>;

  return (
    <div className="users-page">
      <div className="page-header">
        <h1>ユーザ管理</h1>
        <Button variant="primary" size="md" onClick={() => setShowCreate(true)}>
          + 新規ユーザ作成
        </Button>
      </div>

      <div className="users-list">
        {users.map(user => (
          <Card key={user.id} hoverable borderLeft={user.is_active ? undefined : 'danger'}>
            <div className="user-card">
              <div className="user-card__info">
                <div className="user-card__header">
                  <span className="user-card__username">{user.username}</span>
                  <Badge variant={roleBadgeVariant[user.role] || 'info'} size="sm">{user.role}</Badge>
                  {!user.is_active && <Badge variant="danger" size="sm">無効</Badge>}
                  {user.must_change_password && <Badge variant="warning" size="sm">要PW変更</Badge>}
                </div>
                <div className="user-card__details">
                  <span>{user.email}</span>
                  <span>作成: {new Date(user.created_at).toLocaleDateString('ja-JP')}</span>
                </div>
              </div>
              <div className="user-card__actions">
                <Button variant="secondary" size="sm" onClick={() => { setEditUser(user); setEditForm({ email: user.email, role: user.role }); }}>
                  編集
                </Button>
                <Button variant="secondary" size="sm" onClick={() => { setResetUser(user); setResetPassword(''); setResetError(null); }}>
                  PW リセット
                </Button>
                {user.is_active && (
                  <Button variant="danger" size="sm" onClick={() => handleDeactivate(user)}>
                    無効化
                  </Button>
                )}
              </div>
            </div>
          </Card>
        ))}
      </div>

      {/* Create Modal */}
      <Modal isOpen={showCreate} onClose={() => setShowCreate(false)} title="新規ユーザ作成" size="md">
        <form onSubmit={handleCreate} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
          {createError && <div className="login-page__error">{createError}</div>}
          <Input label="ユーザ名 *" value={createForm.username} onChange={v => setCreateForm({ ...createForm, username: v })} placeholder="3文字以上" />
          <Input label="メールアドレス *" value={createForm.email} onChange={v => setCreateForm({ ...createForm, email: v })} placeholder="user@example.com" />
          <div className="input-field">
            <label className="input-field__label">パスワード *</label>
            <input className="input-field__input" type="password" value={createForm.password} onChange={e => setCreateForm({ ...createForm, password: e.target.value })} placeholder="8文字以上、英大文字・小文字・数字" />
          </div>
          <Select label="ロール" value={createForm.role} onChange={v => setCreateForm({ ...createForm, role: v })} options={roleOptions} />
          <Button variant="primary" size="md" type="submit" loading={creating} disabled={creating}>作成</Button>
        </form>
      </Modal>

      {/* Edit Modal */}
      <Modal isOpen={!!editUser} onClose={() => setEditUser(null)} title={`ユーザ編集: ${editUser?.username}`} size="md">
        <form onSubmit={handleEdit} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
          {editError && <div className="login-page__error">{editError}</div>}
          <Input label="メールアドレス" value={editForm.email} onChange={v => setEditForm({ ...editForm, email: v })} />
          <Select label="ロール" value={editForm.role} onChange={v => setEditForm({ ...editForm, role: v })} options={roleOptions} />
          <Button variant="primary" size="md" type="submit" loading={editing} disabled={editing}>更新</Button>
        </form>
      </Modal>

      {/* Reset Password Modal */}
      <Modal isOpen={!!resetUser} onClose={() => setResetUser(null)} title={`パスワードリセット: ${resetUser?.username}`} size="md">
        <form onSubmit={handleResetPassword} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
          {resetError && <div className="login-page__error">{resetError}</div>}
          <div className="input-field">
            <label className="input-field__label">新しいパスワード *</label>
            <input className="input-field__input" type="password" value={resetPassword} onChange={e => setResetPassword(e.target.value)} placeholder="8文字以上、英大文字・小文字・数字" />
          </div>
          <p style={{ fontSize: 'var(--font-sm)', color: 'var(--color-text-secondary)' }}>リセット後、ユーザは次回ログイン時にパスワード変更を求められます。</p>
          <Button variant="primary" size="md" type="submit" loading={resetting} disabled={resetting}>リセット</Button>
        </form>
      </Modal>
    </div>
  );
};

export default Users;
