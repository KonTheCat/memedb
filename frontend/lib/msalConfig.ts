import { PublicClientApplication, type Configuration } from "@azure/msal-browser";

const msalConfig: Configuration = {
  auth: {
    clientId: process.env.NEXT_PUBLIC_ENTRA_CLIENT_ID ?? "",
    authority: process.env.NEXT_PUBLIC_ENTRA_AUTHORITY ?? "",
    redirectUri: typeof window !== "undefined" ? window.location.origin : undefined,
    knownAuthorities: process.env.NEXT_PUBLIC_ENTRA_AUTHORITY ? [new URL(process.env.NEXT_PUBLIC_ENTRA_AUTHORITY).host] : [],
  },
  cache: {
    cacheLocation: "sessionStorage",
  },
};

export const msalInstance = new PublicClientApplication(msalConfig);

export const loginRequest = {
  scopes: [`${process.env.NEXT_PUBLIC_ENTRA_CLIENT_ID ?? ""}/.default`],
};

// Entra External ID supports sending new users directly to the create-account
// experience (skipping the sign-in page) via the "prompt=create" query param.
export const signUpRequest = {
  ...loginRequest,
  extraQueryParameters: { prompt: "create" },
};
