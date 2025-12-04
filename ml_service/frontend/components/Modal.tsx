'use client';

import React, { useEffect } from 'react';
import styles from './Modal.module.css';

export type ModalType = 'alert' | 'confirm' | 'info' | 'success' | 'error';

export interface ModalProps {
  isOpen: boolean;
  type: ModalType;
  title?: string;
  message: string;
  onConfirm?: () => void;
  onCancel?: () => void;
  confirmText?: string;
  cancelText?: string;
}

export default function Modal({
  isOpen,
  type,
  title,
  message,
  onConfirm,
  onCancel,
  confirmText,
  cancelText,
}: ModalProps) {
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [isOpen]);

  if (!isOpen) return null;

  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget && type === 'alert') {
      onConfirm?.();
    }
  };

  const defaultTitle = type === 'confirm' 
    ? 'Подтверждение'
    : type === 'error'
    ? 'Ошибка'
    : type === 'success'
    ? 'Успешно'
    : 'Информация';

  const defaultConfirmText = type === 'confirm' ? 'Подтвердить' : 'OK';
  const defaultCancelText = 'Отмена';

  return (
    <div className={styles.backdrop} onClick={handleBackdropClick}>
      <div className={`${styles.modal} ${styles[`modal-${type}`]}`}>
        <div className={styles.header}>
          <h3 className={styles.title}>{title || defaultTitle}</h3>
        </div>
        <div className={styles.body}>
          <p className={styles.message}>{message}</p>
        </div>
        <div className={styles.footer}>
          {type === 'confirm' && onCancel && (
            <button
              className={`${styles.button} ${styles.cancelButton}`}
              onClick={onCancel}
            >
              {cancelText || defaultCancelText}
            </button>
          )}
          <button
            className={`${styles.button} ${styles[`confirmButton-${type}`]}`}
            onClick={onConfirm}
          >
            {confirmText || defaultConfirmText}
          </button>
        </div>
      </div>
    </div>
  );
}

