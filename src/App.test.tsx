// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import App from "./App";

describe("App", () => {
  it("renders both primary workspace areas", () => {
    render(<App />);

    expect(screen.getByRole("heading", { name: "WiseTodo" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Chat" })).toBeInTheDocument();
  });
});
