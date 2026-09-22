import { resolve } from "path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      input: {
        main: resolve(process.cwd(), "index.html"),
        employer: resolve(process.cwd(), "employer.html"),
        auth: resolve(process.cwd(), "auth.html"),
        nearby: resolve(process.cwd(), "nearby.html"),
        employerOnboarding: resolve(process.cwd(), "employer-onboarding.html")
      }
    }
  },
  server: {
    host: "0.0.0.0",
    port: 5173
  }
});
