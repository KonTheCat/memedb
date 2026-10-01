"use client";

import Link from "next/link";
import { useMsal } from "@azure/msal-react";
import { isAdmin } from "@/lib/auth";
import styles from "./CalibrateLink.module.css";

export default function CalibrateLink() {
  const { accounts } = useMsal();
  if (!isAdmin(accounts[0])) return null;

  return (
    <Link href="/calibrate" className={styles.link}>
      Calibrate
    </Link>
  );
}
