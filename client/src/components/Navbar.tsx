import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Activity, LogOut, User as UserIcon } from "lucide-react";
import { useAuth } from "../pages/AuthContext";
import { auth } from "../pages/firebase"; 
import { signOut } from "firebase/auth";

const Navbar = () => {
  const navigate = useNavigate();
  const { user } = useAuth();

  const handleLogout = async () => {
    try {
      await signOut(auth);
      navigate("/login");
    } catch (error) {
      console.error("Logout error:", error);
    }
  };

  return (
    <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container mx-auto px-4 h-16 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2">
          <Activity className="h-6 w-6 text-primary" />
          <span className="text-xl font-bold text-foreground">
            MedRisk <span className="text-primary">AI</span>
          </span>
        </Link>

        <nav className="hidden md:flex items-center gap-4">
          <Link
            to="/"
            className="text-sm font-medium text-muted-foreground hover:text-primary transition-colors"
          >
            Dashboard
          </Link>
          <Link
            to="/upload"
            className="text-sm font-medium text-muted-foreground hover:text-primary transition-colors"
          >
            Upload Report
          </Link>
          <Link
            to="/history"
            className="text-sm font-medium text-muted-foreground hover:text-primary transition-colors"
          >
            My History
          </Link>
          <Link
            to="/find-doctor"
            className="text-sm font-medium text-muted-foreground hover:text-primary transition-colors"
          >
            Find a Doctor
          </Link>
        </nav>

        <div className="flex items-center gap-2">
          {user ? (
            <>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => navigate("/profile")}
              >
                <UserIcon className="mr-2 h-4 w-4" />
                {user.displayName || "Profile"}
              </Button>
              <Button variant="outline" size="sm" onClick={handleLogout}>
                <LogOut className="mr-2 h-4 w-4" />
                Logout
              </Button>
            </>
          ) : (
            <>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => navigate("/login")}
              >
                Login
              </Button>
              <Button size="sm" onClick={() => navigate("/register")}>
                Register
              </Button>
            </>
          )}
        </div>
      </div>
    </header>
  );
};

export default Navbar;