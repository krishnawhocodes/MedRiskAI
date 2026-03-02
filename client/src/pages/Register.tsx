import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Activity, MapPin } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { auth, db, appId } from "./firebase";
import { createUserWithEmailAndPassword, updateProfile } from "firebase/auth";
import { doc, serverTimestamp, setDoc } from "firebase/firestore";

const emailLooksValid = (email: string) =>
  /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);

const friendlyAuthError = (err: any): string => {
  const code = String(err?.code || "");
  const msg = String(err?.message || "");

  // Firebase Auth common codes
  if (code === "auth/email-already-in-use")
    return "This email is already registered.";
  if (code === "auth/invalid-email")
    return "Please enter a valid email address.";
  if (code === "auth/weak-password")
    return "Password is too weak. Use at least 6 characters.";
  if (
    code === "auth/operation-not-allowed" ||
    code === "auth/admin-restricted-operation"
  ) {
    return "Email/Password sign-up is disabled in Firebase. Enable it in Firebase Console → Authentication → Sign-in method.";
  }
  if (code === "auth/network-request-failed")
    return "Network error. Check your internet and try again.";
  if (code === "auth/too-many-requests")
    return "Too many attempts. Please wait and try again.";

  // API key / restriction style messages
  if (msg.toLowerCase().includes("api key not valid")) {
    return "Firebase API key is not valid or is restricted. Check Google Cloud API key restrictions (allow localhost) and Identity Toolkit API access.";
  }
  if (
    msg.toLowerCase().includes("blocked") &&
    msg.toLowerCase().includes("referer")
  ) {
    return "Request blocked by API key referrer restrictions. Add your domain (e.g., http://localhost:8080) to allowed referrers.";
  }

  return "Registration failed. Please verify your email/password and try again.";
};

const Register = () => {
  const navigate = useNavigate();
  const { toast } = useToast();

  const [formData, setFormData] = useState({
    fullName: "",
    email: "",
    mobile: "",
    password: "",
    confirmPassword: "",
    location: "",
  });

  const [isLocating, setIsLocating] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const handleAutoLocation = () => {
    setIsLocating(true);

    if (!("geolocation" in navigator)) {
      toast({
        title: "Not Supported",
        description: "Geolocation is not supported by your browser.",
        variant: "destructive",
      });
      setIsLocating(false);
      return;
    }

    navigator.geolocation.getCurrentPosition(
      async (position) => {
        try {
          const response = await fetch(
            `https://nominatim.openstreetmap.org/reverse?lat=${position.coords.latitude}&lon=${position.coords.longitude}&format=json`,
          );
          const data = await response.json();

          const city =
            data?.address?.city ||
            data?.address?.town ||
            data?.address?.village ||
            "Unknown";

          setFormData((p) => ({ ...p, location: city }));

          toast({
            title: "Location detected",
            description: `Your location is set to ${city}`,
          });
        } catch {
          toast({
            title: "Location Error",
            description: "Could not detect your city.",
            variant: "destructive",
          });
        } finally {
          setIsLocating(false);
        }
      },
      () => {
        toast({
          title: "Location Error",
          description: "Please enable location permissions.",
          variant: "destructive",
        });
        setIsLocating(false);
      },
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    const fullName = formData.fullName.trim();
    const email = formData.email.trim(); // trim spaces (very common cause)
    const password = formData.password;
    const confirmPassword = formData.confirmPassword;
    const location = formData.location.trim();
    const mobile = formData.mobile.trim();

    // --- Validation (prevents most 400s) ---
    if (fullName.length < 2) {
      toast({
        title: "Error",
        description: "Please enter your full name.",
        variant: "destructive",
      });
      return;
    }
    if (!emailLooksValid(email)) {
      toast({
        title: "Error",
        description: "Please enter a valid email.",
        variant: "destructive",
      });
      return;
    }
    if (password.length < 6) {
      toast({
        title: "Error",
        description: "Password must be at least 6 characters.",
        variant: "destructive",
      });
      return;
    }
    if (password !== confirmPassword) {
      toast({
        title: "Error",
        description: "Passwords do not match.",
        variant: "destructive",
      });
      return;
    }
    if (!location) {
      toast({
        title: "Error",
        description: "Please enter your city (for doctor search).",
        variant: "destructive",
      });
      return;
    }

    setIsLoading(true);
    try {
      const userCredential = await createUserWithEmailAndPassword(
        auth,
        email,
        password,
      );

      // Display name in Firebase Auth profile
      await updateProfile(userCredential.user, { displayName: fullName });

      // Optional: Save profile in Firestore (does not block signup if it fails)
      try {
        const uid = userCredential.user.uid;
        const profileRef = doc(db, `artifacts/${appId}/users/${uid}/profile`);
        await setDoc(
          profileRef,
          {
            uid,
            fullName,
            email,
            mobile: mobile || null,
            location,
            createdAt: serverTimestamp(),
          },
          { merge: true },
        );
      } catch (profileErr) {
        console.warn("Profile save failed (non-blocking):", profileErr);
      }

      toast({
        title: "Account Created",
        description: "Welcome to MedRisk AI! Please log in.",
      });

      navigate("/login");
    } catch (error: any) {
      console.error("Register error:", error);
      toast({
        title: "Registration Failed",
        description: friendlyAuthError(error),
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-secondary/30 px-4 py-12">
      <div className="w-full max-w-md">
        <div className="flex justify-center mb-8">
          <div className="flex items-center gap-2">
            <Activity className="h-8 w-8 text-primary" />
            <span className="text-2xl font-bold text-foreground">
              MedRisk <span className="text-primary">AI</span>
            </span>
          </div>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Create an Account</CardTitle>
            <CardDescription>
              Get started by creating your free account
            </CardDescription>
          </CardHeader>

          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="fullName">Full Name</Label>
                <Input
                  id="fullName"
                  type="text"
                  placeholder="John Doe"
                  value={formData.fullName}
                  onChange={(e) =>
                    setFormData((p) => ({ ...p, fullName: e.target.value }))
                  }
                  required
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="email">Email Address</Label>
                <Input
                  id="email"
                  type="email"
                  placeholder="name@example.com"
                  value={formData.email}
                  onChange={(e) =>
                    setFormData((p) => ({ ...p, email: e.target.value }))
                  }
                  required
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="location">Your City (for Doctor Search)</Label>
                <div className="flex gap-2">
                  <Input
                    id="location"
                    type="text"
                    placeholder="e.g. Indore"
                    value={formData.location}
                    onChange={(e) =>
                      setFormData((p) => ({ ...p, location: e.target.value }))
                    }
                    required
                  />
                  <Button
                    type="button"
                    variant="outline"
                    onClick={handleAutoLocation}
                    disabled={isLocating}
                  >
                    <MapPin
                      className={`h-4 w-4 ${isLocating ? "animate-pulse" : ""}`}
                    />
                  </Button>
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="mobile">Mobile (optional)</Label>
                <Input
                  id="mobile"
                  type="tel"
                  placeholder="Optional"
                  value={formData.mobile}
                  onChange={(e) =>
                    setFormData((p) => ({ ...p, mobile: e.target.value }))
                  }
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="password">Create Password</Label>
                <Input
                  id="password"
                  type="password"
                  placeholder="At least 6 characters"
                  value={formData.password}
                  onChange={(e) =>
                    setFormData((p) => ({ ...p, password: e.target.value }))
                  }
                  required
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="confirmPassword">Confirm Password</Label>
                <Input
                  id="confirmPassword"
                  type="password"
                  placeholder="Re-enter your password"
                  value={formData.confirmPassword}
                  onChange={(e) =>
                    setFormData((p) => ({
                      ...p,
                      confirmPassword: e.target.value,
                    }))
                  }
                  required
                />
              </div>

              <Button type="submit" className="w-full" disabled={isLoading}>
                {isLoading ? "Creating Account..." : "Create Account"}
              </Button>

              <div className="text-center text-sm">
                <span className="text-muted-foreground">
                  Already have an account?{" "}
                </span>
                <Link
                  to="/login"
                  className="text-primary hover:underline font-medium"
                >
                  Login
                </Link>
              </div>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default Register;
