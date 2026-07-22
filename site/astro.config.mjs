import { defineConfig } from 'astro/config';

export default defineConfig({
  site: 'https://www.sdstemecosystem.org',
  // Non-default dev port so `just dev` doesn't collide with other local Astro sites.
  server: { port: 4322 },
});
