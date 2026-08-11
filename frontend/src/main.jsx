import React from "react";
import { createRoot } from "react-dom/client";
import { AcquisitionCalculatorPage, CalculatorLauncher } from "./AcquisitionCalculatorPage";
import { App } from "./App";
import "./styles.css";

const calculatorRoute = window.location.pathname.replace(/\/+$/, "") === "/calculator";
const apiBase = import.meta.env.VITE_API_BASE || "https://api.businessaios.ru";

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    {calculatorRoute ? <AcquisitionCalculatorPage apiBase={apiBase} /> : <><App /><CalculatorLauncher /></>}
  </React.StrictMode>
);
