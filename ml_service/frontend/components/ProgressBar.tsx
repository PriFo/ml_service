'use client';

import React from 'react';
import styles from './ProgressBar.module.css';

interface ProgressBarProps {
  progress: number; // 0-100
  status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';
  color?: string;
}

export default function ProgressBar({ progress, status, color }: ProgressBarProps) {
  // Determine color based on status if not provided
  const getStatusColor = () => {
    if (color) return color;
    
    switch (status) {
      case 'queued':
        return '#ccc';
      case 'running':
        return '#218d81';
      case 'completed':
        return '#22c55e';
      case 'failed':
        return '#ef4444';
      case 'cancelled':
        return '#6b7280';
      default:
        return '#ccc';
    }
  };

  const barColor = getStatusColor();
  const clampedProgress = Math.max(0, Math.min(100, progress));

  return (
    <div className={styles.progressBarContainer}>
      <div className={styles.progressBarBackground}>
        <div
          className={styles.progressBarFill}
          style={{
            width: `${clampedProgress}%`,
            backgroundColor: barColor,
          }}
        />
      </div>
      <span className={styles.progressText}>{clampedProgress}%</span>
    </div>
  );
}

