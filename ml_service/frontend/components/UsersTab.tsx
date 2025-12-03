'use client';

import React, { useState, useEffect } from 'react';
import { useAppStore } from '@/lib/store';
import { api } from '@/lib/api';
import styles from './UsersTab.module.css';

interface User {
  user_id: string;
  username: string;
  tier: string;
  created_at: string;
  last_login: string | null;
  is_active: boolean;
}

export default function UsersTab() {
  const { state, dispatch } = useAppStore();
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [filterTier, setFilterTier] = useState<string>('');
  const [filterActive, setFilterActive] = useState<boolean | null>(null);
  const [currentUserId, setCurrentUserId] = useState<string | null>(null);

  // Form state
  const [formUsername, setFormUsername] = useState('');
  const [formPassword, setFormPassword] = useState('');
  const [formTier, setFormTier] = useState('user');
  const [formIsActive, setFormIsActive] = useState(true);

  const isAdmin = state.userTier === 'admin' || state.userTier === 'system_admin';

  useEffect(() => {
    if (isAdmin) {
      loadCurrentUser();
      loadUsers();
    } else {
      setLoading(false);
    }
  }, [isAdmin, filterTier, filterActive]);

  const loadCurrentUser = async () => {
    try {
      const profile = await api.getProfile();
      setCurrentUserId(profile.user_id);
    } catch (error) {
      console.error('Failed to load current user profile:', error);
    }
  };

  const loadUsers = async () => {
    try {
      setLoading(true);
      const response = await api.getUsers(
        filterTier || undefined,
        filterActive !== null ? filterActive : undefined
      );
      setUsers(response.users || []);
    } catch (error: any) {
      console.error('Failed to load users:', error);
      if (error.status === 401 || error.message?.includes('401')) {
        dispatch({ type: 'LOGOUT' });
        if (typeof window !== 'undefined') {
          window.location.href = '/';
        }
      }
    } finally {
      setLoading(false);
    }
  };

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.createUser(formUsername, formPassword, formTier);
      setShowCreateForm(false);
      setFormUsername('');
      setFormPassword('');
      setFormTier('user');
      await loadUsers();
    } catch (error: any) {
      alert(`Ошибка создания пользователя: ${error.message || 'Неизвестная ошибка'}`);
    }
  };

  const handleUpdateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingUser) return;
    try {
      await api.updateUser(editingUser.user_id, formTier, formIsActive);
      setEditingUser(null);
      setFormTier('user');
      setFormIsActive(true);
      await loadUsers();
    } catch (error: any) {
      alert(`Ошибка обновления пользователя: ${error.message || 'Неизвестная ошибка'}`);
    }
  };

  const handleDeleteUser = async (userId: string, username: string) => {
    if (!confirm(`Вы уверены, что хотите удалить пользователя "${username}"?`)) {
      return;
    }
    try {
      await api.deleteUser(userId);
      await loadUsers();
    } catch (error: any) {
      alert(`Ошибка удаления пользователя: ${error.message || 'Неизвестная ошибка'}`);
    }
  };

  const startEdit = (user: User) => {
    setEditingUser(user);
    setFormTier(user.tier);
    setFormIsActive(user.is_active);
  };

  const cancelEdit = () => {
    setEditingUser(null);
    setFormTier('user');
    setFormIsActive(true);
  };

  if (!isAdmin) {
    return (
      <div className={styles.usersTab}>
        <div className={styles.accessDenied}>
          <h2>Доступ запрещен</h2>
          <p>Управление пользователями доступно только администраторам.</p>
        </div>
      </div>
    );
  }

  if (loading) {
    return <div className={styles.loading}>Загрузка...</div>;
  }

  const availableTiers = state.userTier === 'system_admin' 
    ? ['user', 'admin', 'system_admin']
    : ['user', 'admin'];

  return (
    <div className={styles.usersTab}>
      <div className={styles.header}>
        <h2>Управление пользователями</h2>
        <button
          className={styles.createButton}
          onClick={() => {
            setShowCreateForm(true);
            setEditingUser(null);
          }}
        >
          + Создать пользователя
        </button>
      </div>

      <div className={styles.filters}>
        <select
          value={filterTier}
          onChange={(e) => setFilterTier(e.target.value)}
          className={styles.filterSelect}
        >
          <option value="">Все роли</option>
          <option value="user">Пользователь</option>
          <option value="admin">Администратор</option>
          {state.userTier === 'system_admin' && (
            <option value="system_admin">Системный администратор</option>
          )}
        </select>
        <select
          value={filterActive === null ? '' : String(filterActive)}
          onChange={(e) => {
            const value = e.target.value;
            setFilterActive(value === '' ? null : value === 'true');
          }}
          className={styles.filterSelect}
        >
          <option value="">Все статусы</option>
          <option value="true">Активные</option>
          <option value="false">Неактивные</option>
        </select>
      </div>

      {showCreateForm && (
        <div className={styles.formModal}>
          <div className={styles.formContent}>
            <h3>Создать пользователя</h3>
            <form onSubmit={handleCreateUser}>
              <div className={styles.formGroup}>
                <label>Имя пользователя:</label>
                <input
                  type="text"
                  value={formUsername}
                  onChange={(e) => setFormUsername(e.target.value)}
                  required
                />
              </div>
              <div className={styles.formGroup}>
                <label>Пароль:</label>
                <input
                  type="password"
                  value={formPassword}
                  onChange={(e) => setFormPassword(e.target.value)}
                  required
                  minLength={6}
                />
              </div>
              <div className={styles.formGroup}>
                <label>Роль:</label>
                <select
                  value={formTier}
                  onChange={(e) => setFormTier(e.target.value)}
                  required
                >
                  {availableTiers.map(tier => (
                    <option key={tier} value={tier}>
                      {tier === 'user' ? 'Пользователь' : tier === 'admin' ? 'Администратор' : 'Системный администратор'}
                    </option>
                  ))}
                </select>
              </div>
              <div className={styles.formActions}>
                <button type="submit" className={styles.submitButton}>
                  Создать
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setShowCreateForm(false);
                    setFormUsername('');
                    setFormPassword('');
                    setFormTier('user');
                  }}
                  className={styles.cancelButton}
                >
                  Отмена
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {editingUser && (
        <div className={styles.formModal}>
          <div className={styles.formContent}>
            <h3>Редактировать пользователя: {editingUser.username}</h3>
            <form onSubmit={handleUpdateUser}>
              <div className={styles.formGroup}>
                <label>Роль:</label>
                <select
                  value={formTier}
                  onChange={(e) => setFormTier(e.target.value)}
                  required
                >
                  {availableTiers.map(tier => (
                    <option key={tier} value={tier}>
                      {tier === 'user' ? 'Пользователь' : tier === 'admin' ? 'Администратор' : 'Системный администратор'}
                    </option>
                  ))}
                </select>
              </div>
              <div className={styles.formGroup}>
                <label>
                  <input
                    type="checkbox"
                    checked={formIsActive}
                    onChange={(e) => setFormIsActive(e.target.checked)}
                  />
                  Активен
                </label>
              </div>
              <div className={styles.formActions}>
                <button type="submit" className={styles.submitButton}>
                  Сохранить
                </button>
                <button
                  type="button"
                  onClick={cancelEdit}
                  className={styles.cancelButton}
                >
                  Отмена
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      <div className={styles.usersList}>
        {users.length === 0 ? (
          <div className={styles.empty}>Пользователи не найдены</div>
        ) : (
          users.map((user) => (
            <div key={user.user_id} className={styles.userCard}>
              <div className={styles.userInfo}>
                <div className={styles.userHeader}>
                  <h4>{user.username}</h4>
                  <div className={styles.userBadges}>
                    <span className={`${styles.tierBadge} ${styles[`tier${user.tier}`]}`}>
                      {user.tier === 'user' ? 'Пользователь' : user.tier === 'admin' ? 'Администратор' : 'Системный администратор'}
                    </span>
                    {user.is_active ? (
                      <span className={styles.activeBadge}>Активен</span>
                    ) : (
                      <span className={styles.inactiveBadge}>Неактивен</span>
                    )}
                  </div>
                </div>
                <div className={styles.userDetails}>
                  <div>ID: {user.user_id.substring(0, 8)}...</div>
                  <div>Создан: {new Date(user.created_at).toLocaleDateString('ru-RU')}</div>
                  {user.last_login && (
                    <div>Последний вход: {new Date(user.last_login).toLocaleString('ru-RU')}</div>
                  )}
                </div>
              </div>
              <div className={styles.userActions}>
                <button
                  onClick={() => startEdit(user)}
                  className={styles.editButton}
                >
                  Редактировать
                </button>
                {user.user_id !== currentUserId && (
                  <button
                    onClick={() => handleDeleteUser(user.user_id, user.username)}
                    className={styles.deleteButton}
                  >
                    Удалить
                  </button>
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

