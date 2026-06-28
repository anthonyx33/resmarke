import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import MintApp from "./MintApp";
import "./styles.css";
import "./mint.css";

// Lightweight path routing. The Re-Mint It experience is now the production
// home page and also remains available at "/mint".
const path = window.location.pathname;
const isMint = path === "/" || path === "/mint" || path.startsWith("/mint/");
const Root = isMint ? MintApp : App;

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <Root />
  </React.StrictMode>
);
