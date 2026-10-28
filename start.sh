#!/bin/bash

# OCR Invoice Processor - Start Script
# Simple script to start both backend and frontend services

echo "🚀 Starting OCR Invoice Processor..."
echo "=================================="

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠️  No .env file found. Creating from template...${NC}"
    if [ -f "environment.template" ]; then
        cp environment.template .env
        echo -e "${GREEN}✅ Created .env from environment.template${NC}"
        echo -e "${YELLOW}📝 Please edit .env file with your actual configuration before proceeding${NC}"
    else
        echo -e "${RED}❌ No environment.template found!${NC}"
        exit 1
    fi
fi

# Function to check if port is in use
check_port() {
    local port=$1
    local service=$2
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo -e "${YELLOW}⚠️  Port $port is already in use. Stopping existing $service process...${NC}"
        lsof -ti:$port | xargs kill -9 2>/dev/null || true
        sleep 2
    fi
}

# Check and clean ports
echo -e "${BLUE}🔍 Checking ports...${NC}"
check_port 8000 "backend"
check_port 3000 "frontend"

# Start backend
echo -e "${BLUE}🔧 Starting backend server...${NC}"
cd backend

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}📦 Creating Python virtual environment...${NC}"
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate 2>/dev/null || {
    echo -e "${YELLOW}⚠️  Virtual environment not found, using system Python${NC}"
}

# Install dependencies if needed
if [ ! -f "venv/installed" ]; then
    echo -e "${BLUE}📦 Installing Python dependencies...${NC}"
    pip install -r requirements.txt
    touch venv/installed
fi

# Start backend in background
echo -e "${GREEN}🚀 Starting backend on http://localhost:8000${NC}"
python main.py > ../backend.log 2>&1 &
BACKEND_PID=$!

# Wait a moment for backend to start
sleep 3

# Check if backend started successfully
if ps -p $BACKEND_PID > /dev/null; then
    echo -e "${GREEN}✅ Backend started successfully (PID: $BACKEND_PID)${NC}"
else
    echo -e "${RED}❌ Backend failed to start. Check backend.log for errors.${NC}"
    exit 1
fi

# Go back to root and start frontend
cd ..

echo -e "${BLUE}🔧 Starting frontend server...${NC}"
cd frontend

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo -e "${BLUE}📦 Installing Node.js dependencies...${NC}"
    npm install
fi

# The frontend only needs the public backend URL, not the backend secrets
API_URL=$(grep -E '^NEXT_PUBLIC_API_URL=' ../.env | cut -d= -f2-)
echo "NEXT_PUBLIC_API_URL=${API_URL:-http://localhost:8000}" > .env.local
rm -f .env

# Production build (rebuilt only when the code or config changed)
if [ ! -f ".next/BUILD_ID" ] || [ -n "$(find src public next.config.js package.json .env.local -newer .next/BUILD_ID 2>/dev/null | head -1)" ]; then
    echo -e "${BLUE}🏗️  Building frontend (about a minute)...${NC}"
    if ! NODE_ENV=production npm run build > ../frontend-build.log 2>&1; then
        echo -e "${RED}❌ Frontend build failed. Check frontend-build.log for errors.${NC}"
        kill $BACKEND_PID 2>/dev/null
        exit 1
    fi
fi

# Start frontend in background
echo -e "${GREEN}🚀 Starting frontend on http://localhost:3000${NC}"
NODE_ENV=production npm run start > ../frontend.log 2>&1 &
FRONTEND_PID=$!

# Wait a moment for frontend to start
sleep 5

# Check if frontend started successfully
if ps -p $FRONTEND_PID > /dev/null; then
    echo -e "${GREEN}✅ Frontend started successfully (PID: $FRONTEND_PID)${NC}"
else
    echo -e "${RED}❌ Frontend failed to start. Check frontend.log for errors.${NC}"
    kill $BACKEND_PID 2>/dev/null
    exit 1
fi

# Save PIDs for stop script
echo $BACKEND_PID > .backend.pid
echo $FRONTEND_PID > .frontend.pid

cd ..

echo ""
echo "=================================="
echo -e "${GREEN}🎉 OCR Invoice Processor Started Successfully!${NC}"
echo ""
echo -e "${BLUE}📍 Services:${NC}"
echo -e "   Backend:  http://localhost:8000"
echo -e "   Frontend: http://localhost:3000"
echo -e "   API Docs: http://localhost:8000/docs"
echo ""
echo -e "${BLUE}📝 Logs:${NC}"
echo -e "   Backend:  tail -f backend.log"
echo -e "   Frontend: tail -f frontend.log"
echo ""
echo -e "${BLUE}🛑 To stop:${NC}"
echo -e "   Run: ./stop.sh"
echo ""
echo -e "${YELLOW}💡 Tip: Open http://localhost:3000 in your browser to get started!${NC}"
echo "=================================="