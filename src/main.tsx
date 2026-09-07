import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./styles.css";

async function mount() {
  const preview = import.meta.env.DEV && new URLSearchParams(window.location.search).get("preview") === "todos";
  const loadTodos = preview ? (await import("./todos/preview")).loadPreviewTodos : undefined;
  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <App loadTodos={loadTodos} preview={preview} />
    </StrictMode>,
  );
}

void mount();
