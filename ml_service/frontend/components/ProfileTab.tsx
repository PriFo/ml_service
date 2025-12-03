'use client';

import React, { useState, useEffect } from 'react';
import { useAppStore } from '@/lib/store';
import { api } from '@/lib/api';
import styles from './ProfileTab.module.css';

interface Profile {
  user_id: string;
  username: string;
  tier: string;
  created_at: string;
  last_login: string | null;
}

export default function ProfileTab() {
  const { state, dispatch } = useAppStore();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'info' | 'password' | 'username' | 'tokens'>('info');
  const [tokens, setTokens] = useState<any[]>([]);

  // Form states
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [newUsername, setNewUsername] = useState('');
  const [tokenName, setTokenName] = useState('');

  useEffect(() => {
    if (state.isAuthenticated) {
      loadProfile();
      if (activeTab === 'tokens') {
        loadTokens();
      }
    }
  }, [state.isAuthenticated, activeTab]);

  const loadProfile = async () => {
    try {
      setLoading(true);
      const profileData = await api.getProfile();
      setProfile(profileData);
      setNewUsername(profileData.username);
    } catch (error: any) {
      console.error('Failed to load profile:', error);
      if (error.status === 401 || error.message?.includes('401')) {
        dispatch({ type: 'LOGOUT' });
        if (typeof window !== 'undefined') {
          window.location.href = '/';
        }
      } else if (error.status === 404 || error.message?.includes('User not found')) {
        // User not found - might be using system token, try to reload
        console.warn('User not found, might be using system token');
        // Don't show error, just set a default profile
        setProfile({
          user_id: 'system_admin',
          username: 'system_admin',
          tier: 'system_admin',
          created_at: new Date().toISOString(),
          last_login: null,
        });
      }
    } finally {
      setLoading(false);
    }
  };

  const loadTokens = async () => {
    try {
      const response = await api.getTokens();
      setTokens(response.tokens || []);
    } catch (error: any) {
      console.error('Failed to load tokens:', error);
    }
  };

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (newPassword !== confirmPassword) {
      alert('Новые пароли не совпадают');
      return;
    }
    if (newPassword.length < 6) {
      alert('Пароль должен содержать минимум 6 символов');
      return;
    }
    try {
      await api.changePassword(currentPassword, newPassword);
      alert('Пароль успешно изменен');
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (error: any) {
      alert(`Ошибка изменения пароля: ${error.message || 'Неизвестная ошибка'}`);
    }
  };

  const handleChangeUsername = async (e: React.FormEvent) => {
    e.preventDefault();
    if (newUsername === profile?.username) {
      alert('Новое имя пользователя должно отличаться от текущего');
      return;
    }
    try {
      const updatedProfile = await api.changeUsername(newUsername);
      setProfile(updatedProfile);
      dispatch({
        type: 'SET_AUTHENTICATED',
        payload: {
          isAuthenticated: true,
          token: state.userToken,
          tier: updatedProfile.tier,
        },
      });
      alert('Имя пользователя успешно изменено');
    } catch (error: any) {
      alert(`Ошибка изменения имени пользователя: ${error.message || 'Неизвестная ошибка'}`);
    }
  };

  const handleCreateToken = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const response = await api.createToken(tokenName || undefined);
      alert(`Токен создан! Сохраните его сейчас, он больше не будет показан:\n\n${response.token}`);
      setTokenName('');
      await loadTokens();
    } catch (error: any) {
      alert(`Ошибка создания токена: ${error.message || 'Неизвестная ошибка'}`);
    }
  };

  const handleRevokeToken = async (tokenId: string) => {
    if (!confirm('Вы уверены, что хотите отозвать этот токен?')) {
      return;
    }
    try {
      await api.revokeToken(tokenId);
      await loadTokens();
    } catch (error: any) {
      alert(`Ошибка отзыва токена: ${error.message || 'Неизвестная ошибка'}`);
    }
  };

  const handleDeleteToken = async (tokenId: string) => {
    if (!confirm('Вы уверены, что хотите удалить этот токен?')) {
      return;
    }
    try {
      await api.deleteToken(tokenId);
      await loadTokens();
    } catch (error: any) {
      alert(`Ошибка удаления токена: ${error.message || 'Неизвестная ошибка'}`);
    }
  };

  const handleDeleteProfile = async () => {
    if (!confirm('Вы уверены, что хотите удалить свой профиль? Это действие необратимо!')) {
      return;
    }
    try {
      await api.deleteProfile();
      dispatch({ type: 'LOGOUT' });
      if (typeof window !== 'undefined') {
        window.location.href = '/';
      }
    } catch (error: any) {
      alert(`Ошибка удаления профиля: ${error.message || 'Неизвестная ошибка'}`);
    }
  };

  if (loading) {
    return <div className={styles.loading}>Загрузка...</div>;
  }

  if (!profile) {
    return <div className={styles.error}>Не удалось загрузить профиль</div>;
  }

  const tierLabels: Record<string, string> = {
    user: 'Пользователь',
    admin: 'Администратор',
    system_admin: 'Системный администратор',
  };

  return (
    <div className={styles.profileTab}>
      <div className={styles.header}>
        <h2>Мой профиль</h2>
      </div>

      <div className={styles.tabs}>
        <button
          className={`${styles.tab} ${activeTab === 'info' ? styles.active : ''}`}
          onClick={() => setActiveTab('info')}
        >
          Информация
        </button>
        <button
          className={`${styles.tab} ${activeTab === 'password' ? styles.active : ''}`}
          onClick={() => setActiveTab('password')}
        >
          Изменить пароль
        </button>
        <button
          className={`${styles.tab} ${activeTab === 'username' ? styles.active : ''}`}
          onClick={() => setActiveTab('username')}
        >
          Изменить имя
        </button>
        <button
          className={`${styles.tab} ${activeTab === 'tokens' ? styles.active : ''}`}
          onClick={() => {
            setActiveTab('tokens');
            loadTokens();
          }}
        >
          API Токены
        </button>
      </div>

      <div className={styles.content}>
        {activeTab === 'info' && (
          <div className={styles.infoSection}>
            <div className={styles.infoCard}>
              <h3>Основная информация</h3>
              <div className={styles.infoGrid}>
                <div className={styles.infoItem}>
                  <span className={styles.infoLabel}>Имя пользователя:</span>
                  <span className={styles.infoValue}>{profile.username}</span>
                </div>
                <div className={styles.infoItem}>
                  <span className={styles.infoLabel}>Роль:</span>
                  <span className={styles.infoValue}>{tierLabels[profile.tier] || profile.tier}</span>
                </div>
                <div className={styles.infoItem}>
                  <span className={styles.infoLabel}>ID пользователя:</span>
                  <span className={styles.infoValue}>{profile.user_id}</span>
                </div>
                <div className={styles.infoItem}>
                  <span className={styles.infoLabel}>Дата регистрации:</span>
                  <span className={styles.infoValue}>
                    {new Date(profile.created_at).toLocaleString('ru-RU')}
                  </span>
                </div>
                {profile.last_login && (
                  <div className={styles.infoItem}>
                    <span className={styles.infoLabel}>Последний вход:</span>
                    <span className={styles.infoValue}>
                      {new Date(profile.last_login).toLocaleString('ru-RU')}
                    </span>
                  </div>
                )}
              </div>
            </div>

            <div className={styles.dangerZone}>
              <h4>Опасная зона</h4>
              <p>Удаление профиля приведет к полной потере доступа к системе.</p>
              <button
                onClick={handleDeleteProfile}
                className={styles.deleteProfileButton}
              >
                Удалить профиль
              </button>
            </div>
          </div>
        )}

        {activeTab === 'password' && (
          <div className={styles.formSection}>
            <h3>Изменить пароль</h3>
            <form onSubmit={handleChangePassword}>
              <div className={styles.formGroup}>
                <label>Текущий пароль:</label>
                <input
                  type="password"
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  required
                />
              </div>
              <div className={styles.formGroup}>
                <label>Новый пароль:</label>
                <input
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  required
                  minLength={6}
                />
              </div>
              <div className={styles.formGroup}>
                <label>Подтвердите новый пароль:</label>
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  required
                  minLength={6}
                />
              </div>
              <button type="submit" className={styles.submitButton}>
                Изменить пароль
              </button>
            </form>
          </div>
        )}

        {activeTab === 'username' && (
          <div className={styles.formSection}>
            <h3>Изменить имя пользователя</h3>
            <form onSubmit={handleChangeUsername}>
              <div className={styles.formGroup}>
                <label>Новое имя пользователя:</label>
                <input
                  type="text"
                  value={newUsername}
                  onChange={(e) => setNewUsername(e.target.value)}
                  required
                />
              </div>
              <button type="submit" className={styles.submitButton}>
                Изменить имя
              </button>
            </form>
          </div>
        )}

        {activeTab === 'tokens' && (
          <div className={styles.tokensSection}>
            <div className={styles.tokensHeader}>
              <h3>API Токены</h3>
              <button
                onClick={() => {
                  setTokenName('');
                  const form = document.getElementById('createTokenForm');
                  if (form) {
                    (form as HTMLFormElement).scrollIntoView({ behavior: 'smooth' });
                  }
                }}
                className={styles.createTokenButton}
              >
                + Создать токен
              </button>
            </div>

            <form id="createTokenForm" onSubmit={handleCreateToken} className={styles.createTokenForm}>
              <div className={styles.formGroup}>
                <label>Название токена (необязательно):</label>
                <input
                  type="text"
                  value={tokenName}
                  onChange={(e) => setTokenName(e.target.value)}
                  placeholder="Например: Production API"
                />
              </div>
              <button type="submit" className={styles.submitButton}>
                Создать токен
              </button>
            </form>

            <div className={styles.tokensList}>
              {tokens.length === 0 ? (
                <div className={styles.empty}>Токены не найдены</div>
              ) : (
                tokens.map((token) => (
                  <div key={token.token_id} className={styles.tokenCard}>
                    <div className={styles.tokenInfo}>
                      <div className={styles.tokenHeader}>
                        <h4>{token.name || 'Без названия'}</h4>
                        <div className={styles.tokenBadges}>
                          <span className={styles.tokenType}>{token.token_type}</span>
                          {token.is_active ? (
                            <span className={styles.activeBadge}>Активен</span>
                          ) : (
                            <span className={styles.inactiveBadge}>Отозван</span>
                          )}
                        </div>
                      </div>
                      <div className={styles.tokenDetails}>
                        <div>ID: {token.token_id.substring(0, 8)}...</div>
                        <div>Создан: {new Date(token.created_at).toLocaleString('ru-RU')}</div>
                        {token.last_used_at && (
                          <div>Последнее использование: {new Date(token.last_used_at).toLocaleString('ru-RU')}</div>
                        )}
                        {token.expires_at && (
                          <div>Истекает: {new Date(token.expires_at).toLocaleString('ru-RU')}</div>
                        )}
                      </div>
                    </div>
                    <div className={styles.tokenActions}>
                      {token.is_active && (
                        <button
                          onClick={() => handleRevokeToken(token.token_id)}
                          className={styles.revokeButton}
                        >
                          Отозвать
                        </button>
                      )}
                      <button
                        onClick={() => handleDeleteToken(token.token_id)}
                        className={styles.deleteButton}
                      >
                        Удалить
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

