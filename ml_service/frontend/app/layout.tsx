'use client';

import { useEffect } from 'react';
import { AppProvider } from '@/lib/store';
import { themeManager } from '@/lib/theme';
import '../styles/theme.css';
import '../styles/animations.css';
import '../styles/base.css';

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  useEffect(() => {
    // Initialize theme
    themeManager.init();
  }, []);

  return (
    <html lang="ru">
      <body>
        <AppProvider>
          {children}
        </AppProvider>
      </body>
    </html>
  );
}

