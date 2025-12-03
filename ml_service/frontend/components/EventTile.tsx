'use client';

import React from 'react';
import styles from './EventTile.module.css';

interface EventTileProps {
  type: string;
  label: string;
  count: number;
  color: string;
  active: boolean;
  onClick: () => void;
}

export default function EventTile({
  type,
  label,
  count,
  color,
  active,
  onClick,
}: EventTileProps) {
  return (
    <button
      className={`${styles.eventTile} ${active ? styles.active : ''}`}
      style={{
        borderLeftColor: color,
        backgroundColor: active ? `${color}20` : 'transparent',
      }}
      onClick={onClick}
    >
      <div className={styles.tileContent}>
        <div className={styles.tileDot} style={{ backgroundColor: color }} />
        <div className={styles.tileLabel}>{label}</div>
        <div className={styles.tileCount}>{count}</div>
      </div>
    </button>
  );
}

