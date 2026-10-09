import React from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { SupportOperatorConsole } from "./SupportOperatorConsole.jsx";
import { parsePublicEventQuery, PublicEventLanding } from "./PublicEventLanding.jsx";
import "./styles.css";

const publicEvent = parsePublicEventQuery(window.location.search);
const supportConsole = new URLSearchParams(window.location.search).get("support_console") === "1";
const apiBase = import.meta.env.VITE_API_BASE || "https://api.businessaios.ru";

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    {supportConsole ? <SupportOperatorConsole apiBase={apiBase} /> : publicEvent ? <PublicEventLanding apiBase={apiBase} identity={publicEvent} /> : <App />}
  </React.StrictMode>
);
