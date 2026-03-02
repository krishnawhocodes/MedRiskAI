import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { db, appId } from "./firebase";
import { useAuth } from "./AuthContext";
import { doc, onSnapshot, setDoc } from "firebase/firestore";

export type UserLocation = {
  lat: number;
  lng: number;
  accuracy?: number;
  label?: string;
  updatedAt?: number;
};

export type LocationResult = {
  location: UserLocation | null;
  error?: string;
  code?: number; // GeolocationPositionError code
};

type LocationContextType = {
  location: UserLocation | null;
  isLocationReady: boolean;
  requestBrowserLocation: () => Promise<LocationResult>;
  saveManualLocation: (
    label: string,
    lat: number,
    lng: number,
  ) => Promise<void>;
  clearLocation: () => Promise<void>;
};

const LocationContext = createContext<LocationContextType | undefined>(
  undefined,
);

function storageKey(uid: string) {
  return `medrisk_location_${uid}`;
}

function isLocalhostHost() {
  const h = window.location.hostname;
  return h === "localhost" || h === "127.0.0.1";
}

function geoErrorMessage(err: GeolocationPositionError) {
  // code: 1 permission denied, 2 position unavailable, 3 timeout
  if (err.code === 1) {
    return "Location permission denied. Please allow location in browser site settings.";
  }
  if (err.code === 2) {
    return "Location unavailable. Turn ON device location services and try again.";
  }
  if (err.code === 3) {
    return "Location request timed out. Try again (or type your city manually).";
  }
  return err.message || "Could not fetch location.";
}

function getPosition(options: PositionOptions): Promise<GeolocationPosition> {
  return new Promise((resolve, reject) => {
    navigator.geolocation.getCurrentPosition(resolve, reject, options);
  });
}

export function LocationProvider({ children }: { children: React.ReactNode }) {
  const { userId } = useAuth();

  const [location, setLocation] = useState<UserLocation | null>(null);
  const [isLocationReady, setIsLocationReady] = useState(false);

  // Load from localStorage first
  useEffect(() => {
    if (!userId) {
      setLocation(null);
      setIsLocationReady(true);
      return;
    }

    try {
      const raw = localStorage.getItem(storageKey(userId));
      if (raw) {
        const parsed = JSON.parse(raw) as UserLocation;
        if (parsed?.lat && parsed?.lng) setLocation(parsed);
      }
    } catch {
      // ignore
    }
  }, [userId]);

  // Sync from Firestore
  useEffect(() => {
    if (!userId) {
      setIsLocationReady(true);
      return;
    }

    const ref = doc(db, `artifacts/${appId}/users/${userId}/profile/location`);

    const unsub = onSnapshot(
      ref,
      (snap) => {
        const d = snap.data() as any;
        if (d?.lat && d?.lng) {
          const loc: UserLocation = {
            lat: Number(d.lat),
            lng: Number(d.lng),
            accuracy: d.accuracy ? Number(d.accuracy) : undefined,
            label: d.label || "Your Location",
            updatedAt: d.updatedAt || Date.now(),
          };
          setLocation(loc);
          localStorage.setItem(storageKey(userId), JSON.stringify(loc));
        }
        setIsLocationReady(true);
      },
      () => setIsLocationReady(true),
    );

    return () => unsub();
  }, [userId]);

  const requestBrowserLocation = async (): Promise<LocationResult> => {
    // Secure context requirement (except localhost)
    if (!window.isSecureContext && !isLocalhostHost()) {
      return {
        location: null,
        error:
          "Geolocation requires HTTPS. Open the app on http://localhost:5173 (or deploy on HTTPS).",
      };
    }

    if (!("geolocation" in navigator)) {
      return {
        location: null,
        error: "Geolocation is not supported in this browser.",
      };
    }

    // Permission pre-check (if available)
    try {
      const perms = (navigator as any).permissions;
      if (perms?.query) {
        const status = await perms.query({ name: "geolocation" });
        if (status?.state === "denied") {
          return {
            location: null,
            error:
              "Location is blocked for this site. Allow it in browser site settings and refresh.",
            code: 1,
          };
        }
      }
    } catch {
      // ignore
    }

    try {
      // Try fast first (less accurate but quicker)
      let pos: GeolocationPosition | null = null;

      try {
        pos = await getPosition({
          enableHighAccuracy: false,
          timeout: 12000,
          maximumAge: 60_000,
        });
      } catch (e1: any) {
        // Retry with high accuracy if first attempt fails (timeout/unavailable)
        pos = await getPosition({
          enableHighAccuracy: true,
          timeout: 25000,
          maximumAge: 0,
        });
      }

      const loc: UserLocation = {
        lat: pos.coords.latitude,
        lng: pos.coords.longitude,
        accuracy: pos.coords.accuracy,
        label: "Current Location",
        updatedAt: Date.now(),
      };

      // Update UI immediately (don’t wait for Firestore)
      setLocation(loc);
      if (userId) localStorage.setItem(storageKey(userId), JSON.stringify(loc));

      // Save to Firestore in background (best effort)
      (async () => {
        if (!userId) return;
        try {
          const ref = doc(
            db,
            `artifacts/${appId}/users/${userId}/profile/location`,
          );
          await setDoc(ref, loc, { merge: true });
        } catch (e) {
          console.error("Failed to save location:", e);
        }
      })();

      return { location: loc };
    } catch (err: any) {
      const e = err as GeolocationPositionError;
      console.error("Geolocation error:", e?.code, e?.message);
      return { location: null, error: geoErrorMessage(e), code: e?.code };
    }
  };

  const saveManualLocation = async (
    label: string,
    lat: number,
    lng: number,
  ) => {
    const loc: UserLocation = {
      label,
      lat,
      lng,
      updatedAt: Date.now(),
    };

    setLocation(loc);
    if (userId) localStorage.setItem(storageKey(userId), JSON.stringify(loc));

    if (!userId) return;
    const ref = doc(db, `artifacts/${appId}/users/${userId}/profile/location`);
    await setDoc(ref, loc, { merge: true });
  };

  const clearLocation = async () => {
    setLocation(null);
    if (userId) localStorage.removeItem(storageKey(userId));

    if (!userId) return;
    const ref = doc(db, `artifacts/${appId}/users/${userId}/profile/location`);
    await setDoc(ref, { lat: null, lng: null }, { merge: true });
  };

  const value = useMemo(
    () => ({
      location,
      isLocationReady,
      requestBrowserLocation,
      saveManualLocation,
      clearLocation,
    }),
    [location, isLocationReady],
  );

  return (
    <LocationContext.Provider value={value}>
      {children}
    </LocationContext.Provider>
  );
}

export function useUserLocation() {
  const ctx = useContext(LocationContext);
  if (!ctx)
    throw new Error("useUserLocation must be used inside LocationProvider");
  return ctx;
}
