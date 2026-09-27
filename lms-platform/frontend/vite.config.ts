import { defineConfig } from "vite";

export default defineConfig(({ mode }) => ({
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": {
        target:
          process.env.LMS_API_TARGET ??
          (mode === "demo" ? "http://127.0.0.1:8004" : "http://127.0.0.1:8002"),
      },
    },
  },
}));
