// Configuration file for API endpoints
const CONFIG = {
  // Use Render URLs when NODE_ENV is production OR when FORCE_RENDER_URLS is set
  // This allows using Render URLs even in development when needed
  API_BASE_URL: (process.env.NODE_ENV === 'production' || process.env.REACT_APP_FORCE_RENDER_URLS === 'true')
    ? 'https://get-chat-adyb.onrender.com' // Your actual Render URL
    : 'http://localhost:8000',
  
  WEBSOCKET_URL: (process.env.NODE_ENV === 'production' || process.env.REACT_APP_FORCE_RENDER_URLS === 'true')
    ? 'wss://get-chat-adyb.onrender.com/ws' // Your actual Render WebSocket URL
    : 'ws://localhost:8001'
};

export default CONFIG;