import { useState, useCallback } from 'react';

export type ModalType = 'alert' | 'confirm' | 'info' | 'success' | 'error';

export interface ModalState {
  isOpen: boolean;
  type: ModalType;
  title?: string;
  message: string;
  onConfirm?: () => void;
  onCancel?: () => void;
  confirmText?: string;
  cancelText?: string;
}

export function useModal() {
  const [modal, setModal] = useState<ModalState>({
    isOpen: false,
    type: 'alert',
    message: '',
  });

  const showAlert = useCallback((message: string, title?: string) => {
    return new Promise<void>((resolve) => {
      setModal({
        isOpen: true,
        type: 'alert',
        title,
        message,
        onConfirm: () => {
          setModal((prev) => ({ ...prev, isOpen: false }));
          resolve();
        },
      });
    });
  }, []);

  const showConfirm = useCallback(
    (message: string, title?: string): Promise<boolean> => {
      return new Promise((resolve) => {
        setModal({
          isOpen: true,
          type: 'confirm',
          title,
          message,
          onConfirm: () => {
            setModal((prev) => ({ ...prev, isOpen: false }));
            resolve(true);
          },
          onCancel: () => {
            setModal((prev) => ({ ...prev, isOpen: false }));
            resolve(false);
          },
        });
      });
    },
    []
  );

  const showInfo = useCallback((message: string, title?: string) => {
    return new Promise<void>((resolve) => {
      setModal({
        isOpen: true,
        type: 'info',
        title,
        message,
        onConfirm: () => {
          setModal((prev) => ({ ...prev, isOpen: false }));
          resolve();
        },
      });
    });
  }, []);

  const showSuccess = useCallback((message: string, title?: string) => {
    return new Promise<void>((resolve) => {
      setModal({
        isOpen: true,
        type: 'success',
        title,
        message,
        onConfirm: () => {
          setModal((prev) => ({ ...prev, isOpen: false }));
          resolve();
        },
      });
    });
  }, []);

  const showError = useCallback((message: string, title?: string) => {
    return new Promise<void>((resolve) => {
      setModal({
        isOpen: true,
        type: 'error',
        title,
        message,
        onConfirm: () => {
          setModal((prev) => ({ ...prev, isOpen: false }));
          resolve();
        },
      });
    });
  }, []);

  const closeModal = useCallback(() => {
    setModal((prev) => ({ ...prev, isOpen: false }));
  }, []);

  return {
    modal,
    showAlert,
    showConfirm,
    showInfo,
    showSuccess,
    showError,
    closeModal,
  };
}

