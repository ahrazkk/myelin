import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "@fontsource-variable/atkinson-hyperlegible-next";
import "@fontsource-variable/manrope/wght.css"; // clock numerals only: Atkinson's slashed zero reads oddly at 180px
import "./styles.css";
import { Settings } from "./Settings";
import { Wallpaper } from "./Wallpaper";

// Two screens for now: the wallpaper ("/" or "/wallpaper") and settings.
const path = window.location.pathname.replace(/\/+$/, "");
const Screen = path === "/settings" ? Settings : Wallpaper;

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Screen />
  </StrictMode>,
);
