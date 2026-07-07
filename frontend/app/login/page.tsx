"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { checkPassword } from "@/lib/api";
import { storePassword } from "@/lib/auth";
import styles from "./page.module.css";

export default function LoginPage() {
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setChecking(true);
    setError(null);
    try {
      const ok = await checkPassword(password);
      if (!ok) {
        setError("Incorrect password.");
        return;
      }
      storePassword(password);
      router.push("/");
      router.refresh();
    } catch {
      setError("Could not reach the server.");
    } finally {
      setChecking(false);
    }
  }

  return (
    <main className={styles.main}>
      <form className={styles.form} onSubmit={handleSubmit}>
        <h1 className={styles.title}>MemeDB</h1>
        <label className={styles.field}>
          <span>Password</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoFocus
            required
          />
        </label>
        <button type="submit" disabled={checking}>
          {checking ? "Checking…" : "Enter"}
        </button>
        {error && <p className={styles.error}>{error}</p>}
      </form>
    </main>
  );
}
