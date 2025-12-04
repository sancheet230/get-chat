// Configuration file for API endpoints
const CONFIG = {
  // For development, use localhost
  // For production (Vercel), use your Render backend URL
  API_BASE_URL: process.env.NODE_ENV === 'production' 
    ? 'https://get-chat-adyb.onrender.com' // Your actual Render URL
    : 'http://localhost:8000',
  
  WEBSOCKET_URL: process.env.NODE_ENV === 'production'
    ? 'wss://get-chat-adyb.onrender.com/ws' // Your actual Render WebSocket URL
    : 'ws://localhost:8001'
};

export default CONFIG;