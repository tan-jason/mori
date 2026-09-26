import { defineConfig } from "@hey-api/openapi-ts";

export default defineConfig({
  input: "./openapi.json",
  output: "./src",
  plugins: ["@hey-api/typescript", "@hey-api/sdk", "zod"],
  client: "@hey-api/client-fetch",
});
