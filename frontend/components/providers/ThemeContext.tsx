"use client";

/**
 * Re-export everything from ThemeProvider to avoid duplicate/divergent theme providers
 * caused by concurrent PR merges.
 */
export * from "./ThemeProvider";
