import { readFileSync } from "node:fs";
import { expect, it } from "vitest";
import { decodeError, errorMessages } from "./messages";

it("covers every backend WiseTodoError code, with no stale entries", () => {
  const source = readFileSync("backend/wisetodo/errors.py", "utf8");
  const codes = [...source.matchAll(/^ {4}([A-Z_]+) = "[A-Z_]+"$/gm)].map((m) => m[1]);
  expect(codes.length).toBeGreaterThan(20);
  expect(Object.keys(errorMessages).sort()).toEqual(codes.sort());
});
it("ignores private text and handles future codes safely", () => {
  expect(decodeError(JSON.stringify({ code: "MODEL_REQUEST_FAILED", message: "SECRET", details: { key: "SECRET" }, user_message: "SECRET", retryable: true })))
    .toEqual({ code: "MODEL_REQUEST_FAILED", retryable: true });
  expect(decodeError({ code: "FUTURE_CODE", retryable: "true" })).toEqual({ code: "INTERNAL_ERROR", retryable: false });
  expect(decodeError("SECRET")).toBeUndefined();
  expect(decodeError({ message: "SECRET" })).toBeUndefined();
});
