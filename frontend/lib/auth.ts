import { InteractionRequiredAuthError, type AccountInfo } from "@azure/msal-browser";
import { loginRequest, msalInstance } from "./msalConfig";

export async function getAccessToken(): Promise<string | null> {
  const account = msalInstance.getActiveAccount() ?? msalInstance.getAllAccounts()[0];
  if (!account) return null;

  try {
    const result = await msalInstance.acquireTokenSilent({ ...loginRequest, account });
    return result.accessToken;
  } catch (err) {
    if (err instanceof InteractionRequiredAuthError) {
      await msalInstance.loginRedirect(loginRequest);
    }
    return null;
  }
}

// Mirrors require_admin's `claims.get("roles", [])` check in memedb/api/app.py.
// Needed client-side only where a page calls public endpoints itself (so
// there's no backend 403 to fall back on) but should still be admin-only -
// this app has public self-serve sign-up, so being signed in doesn't imply
// being an admin.
export function isAdmin(account: AccountInfo | null | undefined): boolean {
  const roles = (account?.idTokenClaims as { roles?: string[] } | undefined)?.roles ?? [];
  return roles.includes("Admin");
}
