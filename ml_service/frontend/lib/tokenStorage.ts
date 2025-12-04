// Utility for storing and retrieving API tokens in localStorage
// Tokens are stored with their token_id as key

const STORAGE_PREFIX = 'api_token_';

export interface StoredToken {
  token_id: string;
  token: string;
  name: string | null;
  created_at: string;
}

export function saveToken(tokenId: string, token: string, name: string | null, createdAt: string): void {
  if (typeof window === 'undefined') return;
  
  const storedToken: StoredToken = {
    token_id: tokenId,
    token,
    name,
    created_at: createdAt,
  };
  
  localStorage.setItem(`${STORAGE_PREFIX}${tokenId}`, JSON.stringify(storedToken));
}

export function getToken(tokenId: string): StoredToken | null {
  if (typeof window === 'undefined') return null;
  
  const stored = localStorage.getItem(`${STORAGE_PREFIX}${tokenId}`);
  if (!stored) return null;
  
  try {
    return JSON.parse(stored);
  } catch {
    return null;
  }
}

export function getAllTokens(): StoredToken[] {
  if (typeof window === 'undefined') return [];
  
  const tokens: StoredToken[] = [];
  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i);
    if (key && key.startsWith(STORAGE_PREFIX)) {
      try {
        const token = JSON.parse(localStorage.getItem(key) || '{}');
        if (token.token_id && token.token) {
          tokens.push(token);
        }
      } catch {
        // Skip invalid entries
      }
    }
  }
  
  return tokens;
}

export function deleteToken(tokenId: string): void {
  if (typeof window === 'undefined') return;
  localStorage.removeItem(`${STORAGE_PREFIX}${tokenId}`);
}

export function clearAllTokens(): void {
  if (typeof window === 'undefined') return;
  
  const keysToRemove: string[] = [];
  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i);
    if (key && key.startsWith(STORAGE_PREFIX)) {
      keysToRemove.push(key);
    }
  }
  
  keysToRemove.forEach(key => localStorage.removeItem(key));
}

