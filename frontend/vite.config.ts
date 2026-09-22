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
        employerOnboarding: resolve(process.cwd(), "employer-onboarding.html"),
        employerJob: resolve(process.cwd(), "employer-job.html"),
        employerApplicants: resolve(process.cwd(), "employer-applicants.html"),
        applications: resolve(process.cwd(), "applications.html"),
        application: resolve(process.cwd(), "application.html"),
        employerTeam: resolve(process.cwd(), "employer-team.html"),
        invite: resolve(process.cwd(), "invite.html"),
        employerMatches: resolve(process.cwd(), "employer-matches.html")
      }
    }
  },
  server: {
    host: "0.0.0.0",
    port: 5173
  }
});
