import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { AuthProvider } from "./auth";
import "./index.css";

// Cross-cloud API prefix hook: Automatically prefixes /api calls when frontend is deployed on AWS S3/CloudFront
const apiBase = (import.meta.env.VITE_API_URL || "").replace(/\/+$/, "");
if (apiBase) {
  const originalFetch = window.fetch;
  window.fetch = (input, init) => {
    if (typeof input === "string" && input.startsWith("/api")) {
      input = `${apiBase}${input}`;
    }
    return originalFetch(input, init);
  };
}

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <App />
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
);
