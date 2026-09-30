import { defineConfig, loadEnv } from 'vite';
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const target = env.BACKEND_URL || 'http://127.0.0.1:8000';
  return { server: { host: '127.0.0.1', proxy: { '/api': { target, changeOrigin: true }, '/media': { target, changeOrigin: true } } } };
});
