import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  useLocation,
} from "react-router-dom";
import { useAuth } from "../src/pages/AuthContext";
import { Toaster } from "@/components/ui/toaster";

import Login from "../src/pages/Login";
import Register from "../src/pages/Register";
import Dashboard from "../src/pages/Dashboard";
import Upload from "../src/pages/Upload";
import Results from "../src/pages/Results";
import FindDoctor from "../src/pages/FindDoctor";
import History from "../src/pages/History";
import Profile from "../src/pages/Profile";
import NotFound from "../src/pages/NotFound";
import LocationSetup from "../src/pages/LocationSetup";

import {
  LocationProvider,
  useUserLocation,
} from "../src/pages/LocationContext";

const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  const { user, isAuthReady } = useAuth();
  const { isLocationReady } = useUserLocation();
  const loc = useLocation();

  if (!isAuthReady || !isLocationReady) return <div>Loading...</div>;
  if (!user)
    return <Navigate to="/login" replace state={{ from: loc.pathname }} />;

  return <>{children}</>;
};

const AppRoutes = () => {
  return (
    <Routes>
      {/* Public */}
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />

      {/* Optional Location setup (Protected) */}
      <Route
        path="/location"
        element={
          <ProtectedRoute>
            <LocationSetup />
          </ProtectedRoute>
        }
      />

      {/* Protected Routes */}
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <Dashboard />
          </ProtectedRoute>
        }
      />
      <Route
        path="/upload"
        element={
          <ProtectedRoute>
            <Upload />
          </ProtectedRoute>
        }
      />
      <Route
        path="/results"
        element={
          <ProtectedRoute>
            <Results />
          </ProtectedRoute>
        }
      />
      <Route
        path="/find-doctor"
        element={
          <ProtectedRoute>
            <FindDoctor />
          </ProtectedRoute>
        }
      />
      <Route
        path="/history"
        element={
          <ProtectedRoute>
            <History />
          </ProtectedRoute>
        }
      />
      <Route
        path="/profile"
        element={
          <ProtectedRoute>
            <Profile />
          </ProtectedRoute>
        }
      />

      <Route path="*" element={<NotFound />} />
    </Routes>
  );
};

const App = () => {
  return (
    <BrowserRouter>
      <LocationProvider>
        <AppRoutes />
      </LocationProvider>
      <Toaster />
    </BrowserRouter>
  );
};

export default App;
