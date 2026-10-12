import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The dashboard calls the FastAPI backend directly at http://localhost:8000 (CORS is enabled there).
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, strictPort: true },
});
