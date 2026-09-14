import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath } from 'node:url';
import config from '../app.json';
export default defineConfig({root:fileURLToPath(new URL('.',import.meta.url)),plugins:[react()],server:{host:'127.0.0.1',port:config.web_port,strictPort:true,proxy:{'/api':{target:`http://127.0.0.1:${config.api_port}`,changeOrigin:false}}}});
