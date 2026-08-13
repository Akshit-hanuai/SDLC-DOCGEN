import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { ToastHost } from "./components/ui";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ToastHost />
    <App />
  </StrictMode>,
);
