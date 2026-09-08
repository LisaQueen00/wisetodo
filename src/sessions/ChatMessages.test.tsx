// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import { ChatMessages } from "./ChatMessages";

afterEach(cleanup);
it("renders roles, original text and attachment references without executing markup", () => {
  render(<ChatMessages messages={(["user", "assistant", "system"] as const).map((role, position) => ({
    id: String(position), session_id: "one", position, role, content: "<img src=x onerror=alert(1)>\n原文",
    attachments: position === 0 ? ["D:/book.pdf"] : [], created_at: "date",
  }))} />);
  const list = screen.getByRole("list", { name: "聊天消息" });
  expect(list.children).toHaveLength(3);
  expect(within(list).getByText("你")).toBeInTheDocument();
  expect(within(list).getByText("助手")).toBeInTheDocument();
  expect(within(list).getByText("系统")).toBeInTheDocument();
  expect(list.querySelector("img")).toBeNull();
  expect(screen.getByText("附件：D:/book.pdf")).toBeInTheDocument();
});
