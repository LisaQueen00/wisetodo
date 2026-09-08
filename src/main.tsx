import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { resolveTodoSource } from "./todos/source";
import "./styles.css";
import { desktopSessionApi } from "./sessions/desktop";

async function mount() {
  const { loadTodos, mutations, preview } = await resolveTodoSource(window.location.search);
  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <App loadTodos={loadTodos} mutations={mutations} preview={preview} sessionApi={mutations && !preview ? desktopSessionApi : undefined} />
    </StrictMode>,
  );
}

void mount();
