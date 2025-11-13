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
      watch: {
      usePolling: true,  // 파일 변화를 폴링 방식으로 감지
      interval: 100,     // 100ms마다 체크
    },
  }
})
