import { useState } from "react";
import { useNavigate } from "react-router-dom";

import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { MapPin, Loader2 } from "lucide-react";

import { useUserLocation } from "./LocationContext";
import { useToast } from "@/hooks/use-toast";

export default function LocationSetup() {
  const navigate = useNavigate();
  const { toast } = useToast();
  const { location, requestBrowserLocation, saveManualLocation } =
    useUserLocation();

  const [manualQuery, setManualQuery] = useState("");
  const [loading, setLoading] = useState(false);

  const handleAllowLocation = async () => {
    setLoading(true);
    const loc = await requestBrowserLocation();
    setLoading(false);

    if (loc) {
      toast({
        title: "Location Saved ✅",
        description: "We’ll recommend doctors near you after report analysis.",
      });
      navigate("/");
    } else {
      toast({
        title: "Location Not Granted",
        description: "You can enter your city/pincode manually below.",
        variant: "destructive",
      });
    }
  };

  const handleManual = async () => {
    if (!manualQuery.trim()) return;

    setLoading(true);

    try {
      // ✅ OpenStreetMap geocode (no key)
      const res = await fetch(
        `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(
          manualQuery,
        )}&limit=1`,
      );

      const data = await res.json();

      if (!Array.isArray(data) || data.length === 0) {
        throw new Error("Location not found. Try a different city/pincode.");
      }

      const first = data[0];
      const lat = Number(first.lat);
      const lng = Number(first.lon);

      await saveManualLocation(manualQuery.trim(), lat, lng);

      toast({
        title: "Location Saved ✅",
        description: `Using: ${manualQuery.trim()}`,
      });

      navigate("/");
    } catch (e: any) {
      toast({
        title: "Manual Location Failed",
        description: e?.message || "Try again.",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col">
      <Navbar />

      <main className="flex-1 container mx-auto px-4 py-12 flex items-center justify-center">
        <div className="w-full max-w-xl">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <MapPin className="h-5 w-5 text-primary" />
                Enable Your Location
              </CardTitle>
              <CardDescription>
                We use your location only to recommend doctors near you and show
                them on a map.
              </CardDescription>
            </CardHeader>

            <CardContent className="space-y-5">
              {location ? (
                <div className="rounded-lg border p-4 bg-accent">
                  <p className="text-sm text-muted-foreground">
                    Saved Location
                  </p>
                  <p className="font-semibold text-foreground">
                    {location.label || "Your Location"} (
                    {location.lat.toFixed(4)}, {location.lng.toFixed(4)})
                  </p>
                  <Button className="mt-3 w-full" onClick={() => navigate("/")}>
                    Continue
                  </Button>
                </div>
              ) : (
                <>
                  <Button
                    className="w-full"
                    onClick={handleAllowLocation}
                    disabled={loading}
                  >
                    {loading ? (
                      <>
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                        Getting Location...
                      </>
                    ) : (
                      "Allow Location Permission"
                    )}
                  </Button>

                  <div className="text-center text-xs text-muted-foreground">
                    OR enter location manually (city / pincode)
                  </div>

                  <div className="flex gap-2">
                    <Input
                      placeholder="e.g. Delhi, 110001, Gwalior..."
                      value={manualQuery}
                      onChange={(e) => setManualQuery(e.target.value)}
                      disabled={loading}
                    />
                    <Button
                      variant="outline"
                      onClick={handleManual}
                      disabled={loading}
                    >
                      Use
                    </Button>
                  </div>
                </>
              )}

              <p className="text-xs text-muted-foreground">
                ✅ You can change this later anytime by revisiting this page.
              </p>
            </CardContent>
          </Card>
        </div>
      </main>

      <Footer />
    </div>
  );
}
