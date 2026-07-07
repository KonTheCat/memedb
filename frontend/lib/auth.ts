export const AUTH_COOKIE = "memedb_auth";

export function getStoredPassword(): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(new RegExp(`(?:^|; )${AUTH_COOKIE}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

export function storePassword(password: string): void {
  const maxAge = 60 * 60 * 24 * 30; // 30 days
  document.cookie = `${AUTH_COOKIE}=${encodeURIComponent(password)}; path=/; max-age=${maxAge}; samesite=lax`;
}

export function clearStoredPassword(): void {
  document.cookie = `${AUTH_COOKIE}=; path=/; max-age=0; samesite=lax`;
}
