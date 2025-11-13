import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { GoogleOAuthProvider } from '@react-oauth/google';
import './index.css'
import App from './App.jsx'

const CLIENT_ID = "958080308619-8urh3nnchlmbof3e3hv6kkjo8rccbvod.apps.googleusercontent.com";


createRoot(document.getElementById('root')).render(
  <StrictMode>
        <GoogleOAuthProvider clientId={CLIENT_ID}>
            <App />
        </GoogleOAuthProvider>
  </StrictMode>,
)
