import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import fs from 'fs';
import path from 'path'; 

// const certDir = '../cert';

export default defineConfig({
  plugins: [react()],
  server: {
      port: 3000,
      // https: {
      //     key: fs.readFileSync(path.join(certDir, 'key.pem')),
      //     cert: fs.readFileSync(path.join(certDir, 'cert.pem')),
      // },
      // host: true, 
      // allowedHosts: ["vt.ngrok.pro"],
      watch: {
        usePolling: true, 
        interval: 100,   
      },
  }
})
