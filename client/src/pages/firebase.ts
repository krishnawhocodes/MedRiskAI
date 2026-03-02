// client/src/pages/firebase.ts
import { initializeApp } from "firebase/app";
import { getAuth, onAuthStateChanged, type User } from "firebase/auth";
import { getFirestore } from "firebase/firestore";

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY as string,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN as string,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID as string,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET as string,
  messagingSenderId: import.meta.env
    .VITE_FIREBASE_MESSAGING_SENDER_ID as string,
  appId: import.meta.env.VITE_FIREBASE_APP_ID as string,
};

// Fail fast at build/runtime if env vars are missing
for (const [k, v] of Object.entries(firebaseConfig)) {
  if (!v) throw new Error(`Missing Firebase env var for: ${k}`);
}

export const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);
export const db = getFirestore(app);

// used in your Firestore path
export const appId = firebaseConfig.appId;

/**
 * ✅ Required by AuthContext.tsx
 * Keeps your existing AuthContext API unchanged.
 */
export function listenToAuthChanges(callback: (user: User | null) => void) {
  return onAuthStateChanged(auth, callback);
}
