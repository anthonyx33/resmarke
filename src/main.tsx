import React, { Suspense, lazy } from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import MintApp from "./MintApp";
import SlashImage from "./SlashImage";
import "./styles.css";
import "./mint.css";
import "./slash.css";

// Lightweight path routing. The Re-Mint It experience is the production home
// page and also remains available at "/mint". Slash Image (the new
// V8.9 + Quality Finish pipeline) lives at "/slash" and "/slash-image".
// "/cmint" is the V8.9 + Quality Finish console — lazy-loaded (with its own
// stylesheet) so it never weighs on the home-page bundle.
const CmintApp = lazy(() => import("./CmintApp"));

const path = window.location.pathname;
const lowerPath = path.toLowerCase().replace(/\/+$/, "") || "/";
const isCmint = lowerPath === "/cmint" || lowerPath.startsWith("/cmint/");
const isSlash = path === "/slash" || path.startsWith("/slash/");
const isMint = path === "/" || path === "/mint" || path.startsWith("/mint/");
const Root = isCmint ? CmintApp : isSlash ? SlashImage : isMint ? MintApp : App;

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <Suspense fallback={null}>
      <Root />
    </Suspense>
  </React.StrictMode>
);
