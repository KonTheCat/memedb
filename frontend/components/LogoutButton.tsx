"use client";

import { clearStoredPassword } from "@/lib/auth";
import styles from "./LogoutButton.module.css";

export default function LogoutButton() {
  function handleLogout() {
    clearStoredPassword();
    window.location.href = "/login";
  }

  return (
    <button className={styles.button} onClick={handleLogout} type="button">
      Log out
    </button>
  );
}
