/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_AIGC_PROXY_HOST?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
