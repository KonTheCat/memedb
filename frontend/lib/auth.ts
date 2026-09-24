import { InteractionRequiredAuthError } from "@azure/msal-browser";
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
