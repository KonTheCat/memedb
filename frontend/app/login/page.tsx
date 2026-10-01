"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useIsAuthenticated, useMsal } from "@azure/msal-react";
import { loginRequest, signUpRequest } from "@/lib/msalConfig";
import styles from "./page.module.css";

export default function LoginPage() {
  const router = useRouter();
  const { instance } = useMsal();
  const isAuthenticated = useIsAuthenticated();

  useEffect(() => {
    if (isAuthenticated) {
      router.push("/");
      router.refresh();
    }
  }, [isAuthenticated, router]);

  return (
    <main className={styles.main}>
      <div className={styles.form}>
        <h1 className={styles.title}>MemeDB</h1>
        <button type="button" onClick={() => instance.loginRedirect(loginRequest)}>
          Sign in
        </button>
        <button type="button" className={styles.secondary} onClick={() => instance.loginRedirect(signUpRequest)}>
          Sign up
        </button>
      </div>
    </main>
  );
}
