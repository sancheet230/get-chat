# Deploy React Frontend to Vercel

## Quick Deploy Steps:

### 1. Push to GitHub
Make sure your latest code is pushed to GitHub (already done ✅)

### 2. Go to Vercel
1. Visit https://vercel.com
2. Sign up or log in with your GitHub account
3. Click **"Add New..."** → **"Project"**

### 3. Import Repository
1. Find and select your repository: `sancheet230/get-chat`
2. Click **"Import"**

### 4. Configure Project
1. **Framework Preset:** Create React App (should auto-detect)
2. **Root Directory:** `client` (IMPORTANT!)
3. **Build Command:** `npm run build` (auto-filled)
4. **Output Directory:** `build` (auto-filled)
5. **Install Command:** `npm install` (auto-filled)

### 5. Add Environment Variables
Click **"Environment Variables"** and add:

```
REACT_APP_API_URL=https://your-render-api-url.onrender.com
REACT_APP_WS_URL=wss://your-render-api-url.onrender.com
```

**Important:** 
- Replace `your-render-api-url` with your actual Render service URL
- Use `https://` for API URL
- Use `wss://` for WebSocket URL (secure WebSocket)
- Both should point to the SAME Render service (since we're running both servers together)

Example:
```
REACT_APP_API_URL=https://get-chat-api.onrender.com
REACT_APP_WS_URL=wss://get-chat-api.onrender.com
```

### 6. Deploy
1. Click **"Deploy"**
2. Wait 2-3 minutes for build to complete
3. Your app will be live at: `https://your-project-name.vercel.app`

## After Deployment:

### Update Backend CORS
You need to update your backend to allow requests from your Vercel domain.

In `server/main.py`, update the CORS middleware:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://your-project-name.vercel.app"  # Add your Vercel URL
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Then redeploy your Render service.

## Troubleshooting:

### Build Fails
- Check that Root Directory is set to `client`
- Verify all dependencies are in `client/package.json`
- Check build logs for specific errors

### Can't Connect to Backend
- Verify environment variables are set correctly
- Check that URLs use `https://` and `wss://` (not `http://` or `ws://`)
- Verify backend CORS allows your Vercel domain
- Check browser console for errors

### WebSocket Connection Fails
- Ensure you're using `wss://` (secure WebSocket)
- Verify your Render service is running
- Check that port 8001 is accessible
- Note: Render may require WebSocket on the same port as HTTP

## Alternative: Manual Deploy

If automatic detection doesn't work:

1. In Vercel dashboard, go to Project Settings
2. Set **Root Directory:** `client`
3. Override commands:
   - **Build Command:** `npm run build`
   - **Output Directory:** `build`
   - **Install Command:** `npm install`

## Environment Variables Reference

| Variable | Value | Description |
|----------|-------|-------------|
| `REACT_APP_API_URL` | `https://your-api.onrender.com` | Backend API URL |
| `REACT_APP_WS_URL` | `wss://your-api.onrender.com` | WebSocket URL |

## Redeploy

To redeploy after making changes:
1. Push changes to GitHub
2. Vercel automatically redeploys
3. Or manually trigger from Vercel dashboard

## Custom Domain (Optional)

1. Go to Project Settings → Domains
2. Add your custom domain
3. Follow DNS configuration instructions
4. Update environment variables if needed

---

**Note:** Since we're running both API and WebSocket on the same Render service, both URLs should point to the same domain. The WebSocket server runs on port 8001 internally, but Render handles the routing.
