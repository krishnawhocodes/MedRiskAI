import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import Navbar from "../components/Navbar";
import Footer from "../components/Footer";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import {
  ExternalLink,
  Loader2,
  MapPin,
  Navigation,
  Search,
  RefreshCw,
} from "lucide-react";
import { MapContainer, Marker, Popup, TileLayer } from "react-leaflet";
import L from "leaflet";
import markerIcon2x from "leaflet/dist/images/marker-icon-2x.png";
import markerIcon from "leaflet/dist/images/marker-icon.png";
import markerShadow from "leaflet/dist/images/marker-shadow.png";
import { useUserLocation } from "./LocationContext";
import { useToast } from "@/hooks/use-toast";

delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: markerIcon2x,
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
});

const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000"
).replace(/\/+$/, "");

type DoctorPlace = {
  id: string;
  name: string;
  specialty?: string;
  address?: string;
  rating?: number;
  userRatingsTotal?: number;
  website?: string;
  mapsUrl?: string;
  bookingUrl?: string;
  distanceKm?: number;
  distanceMeters?: number;
  location?: { lat: number; lng: number };
};

type CitySuggestion = { label: string; lat: number; lng: number };

function openExternal(url?: string) {
  if (!url) return;
  window.open(url, "_blank", "noopener,noreferrer");
}

function directionsUrl(
  originLat: number,
  originLng: number,
  destLat: number,
  destLng: number,
) {
  return `https://www.google.com/maps/dir/?api=1&origin=${originLat},${originLng}&destination=${destLat},${destLng}`;
}

// ✅ City suggestions (free): OpenStreetMap Nominatim
async function fetchCitySuggestions(q: string): Promise<CitySuggestion[]> {
  const query = q.trim();
  if (query.length < 2) return [];

  const url =
    `https://nominatim.openstreetmap.org/search?format=json&addressdetails=1&limit=7&countrycodes=in` +
    `&q=${encodeURIComponent(query)}`;

  const res = await fetch(url);
  const data = await res.json();
  if (!Array.isArray(data)) return [];

  const out: CitySuggestion[] = [];
  const seen = new Set<string>();

  for (const item of data) {
    const lat = Number(item.lat);
    const lng = Number(item.lon);
    if (!Number.isFinite(lat) || !Number.isFinite(lng)) continue;

    const label = String(item.display_name || query)
      .split(",")
      .slice(0, 4)
      .join(", ")
      .trim();

    if (!label || seen.has(label)) continue;
    seen.add(label);

    out.push({ label, lat, lng });
  }

  return out;
}

export default function FindDoctor() {
  const { toast } = useToast();
  const { location, requestBrowserLocation, saveManualLocation } =
    useUserLocation();

  const [searchParams] = useSearchParams();
  const initialSpecialty = searchParams.get("specialty") || "";

  const [selectedSpecialty, setSelectedSpecialty] = useState(initialSpecialty);

  // ✅ Doctor filter (name/address)
  const [doctorFilter, setDoctorFilter] = useState("");

  // ✅ City selector
  const [cityQuery, setCityQuery] = useState("");
  const [citySuggestions, setCitySuggestions] = useState<CitySuggestion[]>([]);
  const [cityOpen, setCityOpen] = useState(false);
  const [cityBusy, setCityBusy] = useState(false);
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const debounceRef = useRef<number | null>(null);

  const [loading, setLoading] = useState(false);
  const [doctors, setDoctors] = useState<DoctorPlace[]>([]);
  const [error, setError] = useState<string>("");

  const specialtyChips = [
    { label: "All Nearby", value: "" },
    { label: "General Physician", value: "General Physician" },
    { label: "Cardiologist", value: "Cardiologist" },
    { label: "Endocrinologist", value: "Endocrinologist" },
    { label: "Nephrologist", value: "Nephrologist" },
    { label: "Gastroenterologist", value: "Gastroenterologist" },
    { label: "Hematologist", value: "Hematologist" },
    { label: "Pulmonologist", value: "Pulmonologist" },
    { label: "Dermatologist", value: "Dermatologist" },
  ];

  // ✅ close dropdown on outside click
  useEffect(() => {
    const onDown = (e: MouseEvent) => {
      if (!wrapRef.current) return;
      if (!wrapRef.current.contains(e.target as Node)) setCityOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, []);

  // ✅ debounce suggestions
  useEffect(() => {
    if (debounceRef.current) window.clearTimeout(debounceRef.current);

    const q = cityQuery.trim();
    if (q.length < 2) {
      setCitySuggestions([]);
      setCityOpen(false);
      return;
    }

    debounceRef.current = window.setTimeout(async () => {
      try {
        const s = await fetchCitySuggestions(q);
        setCitySuggestions(s);
        setCityOpen(true);
      } catch {
        setCitySuggestions([]);
        setCityOpen(false);
      }
    }, 350);

    return () => {
      if (debounceRef.current) window.clearTimeout(debounceRef.current);
    };
  }, [cityQuery]);

  const fetchDoctors = async () => {
    if (!location) {
      toast({
        title: "Location required",
        description: "Use GPS or select a city first.",
        variant: "destructive",
      });
      return;
    }

    try {
      setError("");
      setLoading(true);

      const isCityMode =
        !!location?.label && location.label !== "Current Location";

      // City -> wider radius and more results
      const radiusKm = isCityMode ? 25 : 10;
      const limit = isCityMode ? 60 : 30;

      const url =
        `${API_BASE_URL}/api/nearby-doctors` +
        `?lat=${location.lat}` +
        `&lng=${location.lng}` +
        `&limit=${limit}` +
        `&radius_km=${radiusKm}` +
        `&specialty=${encodeURIComponent(selectedSpecialty || "")}`;

      const res = await fetch(url);
      const data = await res.json();

      if (!res.ok) throw new Error(data?.detail || "Failed to fetch doctors");

      // ✅ Backward-compatible: backend might return list OR {doctors: list}
      const list: DoctorPlace[] = Array.isArray(data)
        ? data
        : Array.isArray(data?.doctors)
          ? data.doctors
          : [];

      list.sort((a, b) => (a.distanceKm ?? 999999) - (b.distanceKm ?? 999999));

      setDoctors(list);
    } catch (e: any) {
      setDoctors([]);
      setError(e?.message || "Doctor search failed");
      toast({
        title: "Doctor Search Failed",
        description: e?.message || "Check backend connectivity.",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  // Auto-fetch when location / specialty changes
  useEffect(() => {
    if (!location) return;
    // clear doctor filter when location changes (prevents “Gwalior” filter problem)
    setDoctorFilter("");
    fetchDoctors();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location?.lat, location?.lng, selectedSpecialty]);

  const handleUseCurrentLocation = async () => {
    setCityBusy(true);
    const loc = await requestBrowserLocation();
    setCityBusy(false);

    if (!loc) {
      toast({
        title: "Location Not Granted",
        description:
          "Allow location in browser OR select a city from dropdown.",
        variant: "destructive",
      });
      return;
    }

    toast({
      title: "Using Current Location ✅",
      description: "Fetching doctors near you…",
    });
  };

  const handleSelectCity = async (s: CitySuggestion) => {
    setCityOpen(false);
    setCityQuery(s.label);

    setCityBusy(true);
    try {
      await saveManualLocation(s.label, s.lat, s.lng);
      toast({ title: "City Selected ✅", description: `Using: ${s.label}` });
    } catch (e: any) {
      toast({
        title: "Failed to set city",
        description: e?.message || "Try again.",
        variant: "destructive",
      });
    } finally {
      setCityBusy(false);
    }
  };

  const handleCityEnter = async () => {
    const q = cityQuery.trim();
    if (!q) return;

    setCityBusy(true);
    try {
      const s = await fetchCitySuggestions(q);
      if (!s.length)
        throw new Error("City not found. Try another name/pincode.");
      await handleSelectCity(s[0]);
    } catch (e: any) {
      toast({
        title: "City not found",
        description: e?.message || "Try another city/pincode.",
        variant: "destructive",
      });
    } finally {
      setCityBusy(false);
    }
  };

  const filteredDoctors = useMemo(() => {
    const q = doctorFilter.trim().toLowerCase();
    if (!q) return doctors;
    return doctors.filter(
      (d) =>
        (d.name || "").toLowerCase().includes(q) ||
        (d.address || "").toLowerCase().includes(q) ||
        (d.specialty || "").toLowerCase().includes(q),
    );
  }, [doctors, doctorFilter]);

  const center = useMemo(() => {
    if (!location) return [20.5937, 78.9629] as [number, number];
    return [location.lat, location.lng] as [number, number];
  }, [location]);

  return (
    <div className="min-h-screen flex flex-col">
      <Navbar />

      <main className="flex-1 container mx-auto px-4 py-10">
        <div className="max-w-6xl mx-auto">
          <div className="mb-6">
            <h1 className="text-3xl font-bold text-foreground mb-2">
              Doctors Near You
            </h1>
            <p className="text-muted-foreground">
              Showing nearby doctors for:{" "}
              <span className="font-semibold text-foreground">
                {location?.label || "Location not set"}
              </span>
            </p>
          </div>

          {/* ✅ Location controls */}
          <Card className="mb-6">
            <CardHeader>
              <CardTitle>Choose Location</CardTitle>
              <CardDescription>
                Use GPS or pick a city. (This is separate from doctor name
                search.)
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <Button onClick={handleUseCurrentLocation} disabled={cityBusy}>
                {cityBusy ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Getting location...
                  </>
                ) : (
                  "Use my current location"
                )}
              </Button>

              <div ref={wrapRef} className="relative">
                <Input
                  placeholder="Type city / area / pincode (e.g. Gwalior, 474001)"
                  value={cityQuery}
                  onChange={(e) => setCityQuery(e.target.value)}
                  onFocus={() => citySuggestions.length && setCityOpen(true)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") handleCityEnter();
                  }}
                  disabled={cityBusy}
                />

                {cityOpen && citySuggestions.length > 0 && (
                  <div className="absolute z-50 mt-2 w-full rounded-md border bg-background shadow-lg max-h-64 overflow-auto">
                    {citySuggestions.map((s) => (
                      <button
                        key={`${s.label}-${s.lat}-${s.lng}`}
                        type="button"
                        className="w-full text-left px-3 py-2 hover:bg-accent text-sm"
                        onMouseDown={(e) => e.preventDefault()}
                        onClick={() => handleSelectCity(s)}
                      >
                        {s.label}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </CardContent>
          </Card>

          {/* ✅ Doctor filter + specialty */}
          <Card className="mb-6">
            <CardHeader>
              <CardTitle>Search Doctors</CardTitle>
              <CardDescription>
                Filter results by doctor/clinic name or address (NOT city).
              </CardDescription>
            </CardHeader>

            <CardContent className="space-y-4">
              <div className="flex flex-col md:flex-row gap-3 md:items-center md:justify-between">
                <div className="relative w-full">
                  <Search className="h-4 w-4 absolute left-3 top-3 text-muted-foreground" />
                  <Input
                    className="pl-9"
                    placeholder="Filter doctors by name/address..."
                    value={doctorFilter}
                    onChange={(e) => setDoctorFilter(e.target.value)}
                  />
                </div>

                <Button
                  variant="outline"
                  onClick={fetchDoctors}
                  disabled={loading}
                >
                  <RefreshCw className="h-4 w-4 mr-2" />
                  Refresh
                </Button>
              </div>

              <div className="flex flex-wrap gap-2">
                {specialtyChips.map((sp) => (
                  <Badge
                    key={sp.label}
                    variant={
                      selectedSpecialty === sp.value ? "default" : "outline"
                    }
                    className="cursor-pointer"
                    onClick={() => setSelectedSpecialty(sp.value)}
                  >
                    {sp.label}
                  </Badge>
                ))}
              </div>

              {error && <div className="text-sm text-destructive">{error}</div>}
            </CardContent>
          </Card>

          {/* List + Map */}
          <div className="grid lg:grid-cols-2 gap-6">
            {/* LIST */}
            <Card className="h-fit">
              <CardHeader>
                <CardTitle>Nearby Doctors / Clinics</CardTitle>
                <CardDescription>
                  {loading
                    ? "Loading..."
                    : `${filteredDoctors.length} result(s) found`}
                </CardDescription>
              </CardHeader>

              <CardContent className="space-y-4">
                {loading ? (
                  <div className="flex items-center justify-center py-10">
                    <Loader2 className="h-7 w-7 animate-spin text-primary" />
                  </div>
                ) : filteredDoctors.length === 0 ? (
                  <div className="text-sm text-muted-foreground">
                    No results found.
                    <div className="mt-2 text-xs">
                      Tip: To change city, use the <b>Choose Location</b> box
                      above (don’t type city in filter).
                    </div>
                  </div>
                ) : (
                  filteredDoctors.slice(0, 25).map((d) => {
                    const lat = d.location?.lat;
                    const lng = d.location?.lng;
                    const showDirections =
                      typeof lat === "number" &&
                      typeof lng === "number" &&
                      !!location;
                    const bookUrl = d.bookingUrl || d.website || d.mapsUrl;
                    const mapsUrl = d.mapsUrl;

                    return (
                      <div key={d.id} className="rounded-lg border p-4">
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <p className="font-semibold text-foreground truncate">
                              {d.name}
                            </p>
                            <p className="text-sm text-muted-foreground">
                              {d.specialty || "Doctor / Clinic"}
                            </p>

                            <div className="text-xs text-muted-foreground mt-2 space-y-1">
                              <div className="inline-flex items-center gap-1">
                                <MapPin className="h-3 w-3" />
                                <span className="truncate">
                                  {d.address || "Address not available"}
                                </span>
                              </div>

                              <div className="flex flex-wrap gap-2 mt-1">
                                {typeof d.distanceKm === "number" && (
                                  <Badge variant="outline">
                                    {d.distanceKm.toFixed(2)} km
                                  </Badge>
                                )}
                                {typeof d.rating === "number" && (
                                  <Badge variant="outline">
                                    ⭐ {d.rating.toFixed(1)}
                                    {typeof d.userRatingsTotal === "number"
                                      ? ` (${d.userRatingsTotal})`
                                      : ""}
                                  </Badge>
                                )}
                              </div>
                            </div>
                          </div>

                          <div className="flex flex-col gap-2">
                            <Button
                              size="sm"
                              onClick={() => openExternal(bookUrl)}
                            >
                              Book Appointment{" "}
                              <ExternalLink className="h-4 w-4 ml-2" />
                            </Button>

                            {showDirections ? (
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() =>
                                  openExternal(
                                    directionsUrl(
                                      location!.lat,
                                      location!.lng,
                                      lat!,
                                      lng!,
                                    ),
                                  )
                                }
                              >
                                Directions{" "}
                                <Navigation className="h-4 w-4 ml-2" />
                              </Button>
                            ) : (
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => openExternal(mapsUrl)}
                              >
                                Open Maps{" "}
                                <ExternalLink className="h-4 w-4 ml-2" />
                              </Button>
                            )}
                          </div>
                        </div>

                        {(d.website || d.mapsUrl) && (
                          <>
                            <Separator className="my-3" />
                            <div className="text-xs text-muted-foreground space-y-1">
                              {d.website && (
                                <div className="truncate">
                                  🌐 Website:{" "}
                                  <span
                                    className="underline cursor-pointer"
                                    onClick={() => openExternal(d.website)}
                                  >
                                    {d.website}
                                  </span>
                                </div>
                              )}
                              {d.mapsUrl && (
                                <div className="truncate">
                                  📍 Maps:{" "}
                                  <span
                                    className="underline cursor-pointer"
                                    onClick={() => openExternal(d.mapsUrl)}
                                  >
                                    Open in Google Maps
                                  </span>
                                </div>
                              )}
                            </div>
                          </>
                        )}
                      </div>
                    );
                  })
                )}

                <p className="text-xs text-muted-foreground">
                  ⚠️ For emergencies, visit the nearest hospital immediately.
                </p>
              </CardContent>
            </Card>

            {/* MAP */}
            <Card>
              <CardHeader>
                <CardTitle>Interactive Map</CardTitle>
                <CardDescription>
                  Click markers to open booking or directions.
                </CardDescription>
              </CardHeader>

              <CardContent className="p-0 overflow-hidden rounded-b-lg">
                <div className="h-[520px] w-full">
                  <MapContainer
                    center={center}
                    zoom={13}
                    scrollWheelZoom
                    className="h-full w-full"
                  >
                    <TileLayer
                      attribution="&copy; OpenStreetMap contributors"
                      url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                    />

                    {location && (
                      <Marker position={[location.lat, location.lng]}>
                        <Popup>
                          <div className="text-sm">
                            <p className="font-semibold">You are here</p>
                            <p className="text-xs text-muted-foreground">
                              {location.label || "Current location"}
                            </p>
                          </div>
                        </Popup>
                      </Marker>
                    )}

                    {filteredDoctors.slice(0, 80).map((d) => {
                      const lat = d.location?.lat;
                      const lng = d.location?.lng;
                      if (typeof lat !== "number" || typeof lng !== "number")
                        return null;

                      const bookUrl = d.bookingUrl || d.website || d.mapsUrl;

                      return (
                        <Marker key={d.id} position={[lat, lng]}>
                          <Popup>
                            <div className="space-y-2">
                              <div>
                                <p className="font-semibold">{d.name}</p>
                                <p className="text-xs text-muted-foreground">
                                  {d.specialty || "Doctor / Clinic"}
                                </p>
                                {typeof d.distanceKm === "number" && (
                                  <p className="text-xs text-muted-foreground">
                                    {d.distanceKm.toFixed(2)} km away
                                  </p>
                                )}
                              </div>

                              <div className="flex gap-2 flex-wrap">
                                <Button
                                  size="sm"
                                  onClick={() => openExternal(bookUrl)}
                                >
                                  Book <ExternalLink className="h-4 w-4 ml-2" />
                                </Button>

                                {location ? (
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    onClick={() =>
                                      openExternal(
                                        directionsUrl(
                                          location.lat,
                                          location.lng,
                                          lat,
                                          lng,
                                        ),
                                      )
                                    }
                                  >
                                    Directions{" "}
                                    <Navigation className="h-4 w-4 ml-2" />
                                  </Button>
                                ) : (
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    onClick={() => openExternal(d.mapsUrl)}
                                  >
                                    Maps{" "}
                                    <ExternalLink className="h-4 w-4 ml-2" />
                                  </Button>
                                )}
                              </div>
                            </div>
                          </Popup>
                        </Marker>
                      );
                    })}
                  </MapContainer>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </main>

      <Footer />
    </div>
  );
}
