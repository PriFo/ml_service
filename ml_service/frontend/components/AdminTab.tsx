'use client';

import AdminPanel from './AdminPanel';
import styles from './AdminTab.module.css';

export default function AdminTab() {
  return (
    <div className={styles.adminTab}>
      <h2 className={styles.title}>Administrator Panel</h2>
      <p className={styles.description}>
        Управление системой, базами данных и административными функциями
      </p>
      <AdminPanel />
    </div>
  );
}

