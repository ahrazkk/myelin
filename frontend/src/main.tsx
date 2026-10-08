import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "@fontsource-variable/atkinson-hyperlegible-next";
import "@fontsource-variable/manrope/wght.css"; // clock numerals only: Atkinson's slashed zero reads oddly at 180px
import "./styles.css";
import "./tools.css";
import { Wallpaper } from "./Wallpaper";

// One screen with tabs. "/settings" still works and opens the Settings tab.
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Wallpaper />
  </StrictMode>,
);
