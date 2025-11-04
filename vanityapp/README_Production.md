# VanityApp — Production Deployment

This package contains a production-ready setup for the VanityApp Telegram Mini App.

## Contents
- backend/: FastAPI backend + your existing bot.py, db.py, payments.py (the bot runs inside the same service)
- frontend/: Vite + React Telegram WebApp (deploy to Vercel)
- README_Production.md: this file

## Quick steps (high-level)

1. **Push to GitHub**
   - Create a new GitHub repository and push the contents of this package.

2. **Deploy backend on Render**
   - Go to https://dashboard.render.com
   - Click "New" → "Web Service"
   - Connect your GitHub repo and select the backend/ folder (root repo is fine)
   - Set:
     - Environment: Python 3
     - Build Command: `pip install -r backend/requirements.txt`
     - Start Command: `sh backend/start.sh`
     - Region: Europe (Frankfurt)
   - In Render's "Environment" section, add environment variables from `backend/.env.example`:
     - `BOT_TOKEN`, `MAIN_WALLET`, `SOLANA_RPC`, etc.
   - Deploy. Render will provide a URL like `https://vanityapp-backend.onrender.com`

3. **Deploy frontend on Vercel**
   - Go to https://vercel.com
   - Import the same GitHub repo, set root to `/frontend`
   - Build command: `npm run build`
   - Output directory: `dist`
   - Add environment variable `VITE_API_BASE` pointing to your Render backend URL, e.g. `https://vanityapp-backend.onrender.com`
   - Deploy. Vercel will give you a secure HTTPS URL, e.g. `https://vanityapp-frontend.vercel.app`

4. **Set the Web App URL in BotFather**
   - Open Telegram and message @BotFather
   - Use the `Edit Bot` → `Bot Settings` → `Web Apps` → set the Web App URL to your Vercel frontend URL
   - Example: `https://vanityapp-frontend.vercel.app`

5. **Test**
   - Open your bot @vanityappbot in Telegram, open the Web App button and test browsing, adding to cart and checkout.
   - When a purchase completes, your bot (running on Render) will send the product media into the user's chat.

## Notes
- Before deploying, update `backend/.env.example` and rename to `.env` or fill the environment variables in Render dashboard.
- The `locimg/` folder is empty. Upload your product media into `backend/locimg/product_<id>/` with filenames.
- For production scaling, consider replacing local media with S3 and updating media URLs.

## Render quick tip (region)
- When creating the Web Service on Render, choose **Europe (Germany - Frankfurt)** as the region.

## Support
If you want, I can:
- Create a GitHub repo for you and push this package (you'll need to authorize).
- Add S3 support for images.
- Add admin UI for uploading product media from the frontend.

Good luck — your VanityApp production package is ready!
