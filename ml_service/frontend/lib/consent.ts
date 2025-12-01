// Cookie consent utilities
export interface Consent {
  essential: boolean;
  analytics: boolean;
  preferences: boolean;
  timestamp: number;
}

const CONSENT_EXPIRY_DAYS = 365;

export function saveConsent(consent: Consent) {
  if (typeof window === 'undefined') return;
  
  // Always save to sessionStorage
  sessionStorage.setItem('consent', JSON.stringify(consent));
  
  // Save to localStorage only if preferences allowed
  if (consent.preferences) {
    localStorage.setItem('consent', JSON.stringify(consent));
  }
}

export function getConsent(): Consent | null {
  if (typeof window === 'undefined') return null;
  
  try {
    // Check sessionStorage first
    const sessionConsent = sessionStorage.getItem('consent');
    if (sessionConsent) {
      const consent = JSON.parse(sessionConsent);
      if (isConsentValid(consent)) {
        return consent;
      }
    }
    
    // Check localStorage
    const localConsent = localStorage.getItem('consent');
    if (localConsent) {
      const consent = JSON.parse(localConsent);
      if (isConsentValid(consent)) {
        return consent;
      }
    }
  } catch (e) {
    console.error('Error reading consent:', e);
  }
  
  return null;
}

function isConsentValid(consent: Consent): boolean {
  if (!consent.timestamp) return false;
  
  const expiryTime = consent.timestamp + (CONSENT_EXPIRY_DAYS * 24 * 60 * 60 * 1000);
  return Date.now() < expiryTime;
}

export function canUseAnalytics(): boolean {
  const consent = getConsent();
  return consent?.analytics ?? false;
}

export function canUsePreferences(): boolean {
  const consent = getConsent();
  return consent?.preferences ?? false;
}

