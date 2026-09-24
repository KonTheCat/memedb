"use client";

import { useMsal } from "@azure/msal-react";
import styles from "./LogoutButton.module.css";

export default function LogoutButton() {
  const { instance } = useMsal();

  return (
    <button className={styles.button} onClick={() => instance.logoutRedirect()} type="button">
      Log out
    </button>
  );
}
