// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { UrlAttachments } from "./UrlAttachments";

afterEach(cleanup);
it.each(["example.com", "javascript:alert(1)", "file:///book.pdf", "https://user:pass@example.com",
  "https://@example.com", "https://example.com:99999", "https://exam ple.com", "https://example.com\\path"])(
  "rejects invalid URL %s", (url) => {
    const onChange = vi.fn();
    render(<UrlAttachments urls={[]} disabled={false} onChange={onChange} />);
    fireEvent.change(screen.getByLabelText("URL 附件"), { target: { value: url } });
    fireEvent.click(screen.getByRole("button", { name: "添加链接" }));
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(onChange).not.toHaveBeenCalled();
  },
);
it("rejects duplicates and locks attachment edits when disabled", () => {
  const onChange = vi.fn();
  const { rerender } = render(<UrlAttachments urls={["https://example.com"]} disabled={false} onChange={onChange} />);
  fireEvent.change(screen.getByLabelText("URL 附件"), { target: { value: " https://example.com " } });
  fireEvent.click(screen.getByRole("button", { name: "添加链接" }));
  expect(screen.getByRole("alert")).toHaveTextContent("此链接已添加");
  expect(onChange).not.toHaveBeenCalled();
  rerender(<UrlAttachments urls={["https://example.com"]} disabled onChange={onChange} />);
  expect(screen.getByLabelText("URL 附件")).toBeDisabled();
  expect(screen.getByLabelText("移除链接 https://example.com")).toBeDisabled();
});
