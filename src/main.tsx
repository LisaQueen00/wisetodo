import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { resolveTodoSource } from "./todos/source";
import "./styles.css";

async function mount() {
  const { loadTodos, mutations, preview } = await resolveTodoSource(window.location.search);
  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <App loadTodos={loadTodos} mutations={mutations} preview={preview} />
    </StrictMode>,
  );
}

void mount();
