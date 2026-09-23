/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_ORIGIN?: string;
  readonly VITE_USE_MOCK_API?: "true" | "false";
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
