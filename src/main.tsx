import React from "react";
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
const path = window.location.pathname;
const isSlash = path === "/slash" || path.startsWith("/slash/");
const isMint = path === "/" || path === "/mint" || path.startsWith("/mint/");
const Root = isSlash ? SlashImage : isMint ? MintApp : App;

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <Root />
  </React.StrictMode>
);
