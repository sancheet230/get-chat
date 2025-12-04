// Configuration file for API endpoints
const CONFIG = {
  // For development, use localhost
  // For production (Vercel), use your Render backend URL
  API_BASE_URL: process.env.NODE_ENV === 'production' 
    ? 'https://your-render-app-url.onrender.com' // TODO: Replace with your actual Render URL
    : 'http://localhost:8000',
  
  WEBSOCKET_URL: process.env.NODE_ENV === 'production'
    ? 'wss://your-render-app-url.onrender.com/ws' // TODO: Replace with your actual Render WebSocket URL
    : 'ws://localhost:8001'
};

export default CONFIG;