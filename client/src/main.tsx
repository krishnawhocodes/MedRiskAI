import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { AuthProvider } from "../src/pages/AuthContext";
import "./index.css";

// ✅ Leaflet styles (required for map rendering)
import "leaflet/dist/leaflet.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <AuthProvider>
      <App />
    </AuthProvider>
  </React.StrictMode>,
);
