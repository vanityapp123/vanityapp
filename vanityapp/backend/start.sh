#!/bin/sh
# Start the bot (payments monitor) in background and then the FastAPI app
# This script is suitable for Render: it will keep running the API in foreground.

# Run bot in background (log to bot.log)
python bot.py > bot.log 2>&1 &

# Start FastAPI with uvicorn
exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers
