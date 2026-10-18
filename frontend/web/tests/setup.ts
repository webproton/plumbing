import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// при globals: false Testing Library не чистит DOM сама
afterEach(() => cleanup());
