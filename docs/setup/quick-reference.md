# 🚀 OCR Invoice Processor - Quick Reference

## Instant Commands

### Start Application
```bash
./docker-manager.sh start
# OR for Windows: docker-manager.bat start
```

### Check Status
```bash
./docker-manager.sh status
```

### View Logs
```bash
./docker-manager.sh logs
```

### Stop Application
```bash
./docker-manager.sh stop
```

## 🌐 Application URLs

- **Main Application**: http://localhost:3000
- **API Endpoints**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **API Health Check**: http://localhost:8000/api/health

## 🔄 Quick Workflows

### Daily Startup
1. Open terminal
2. Run: `./docker-manager.sh start`
3. Wait for "🎉 OCR Invoice Processor is now running!"
4. Open browser to http://localhost:3000

### Daily Shutdown
1. Run: `./docker-manager.sh stop`
2. Wait for "Services stopped."

### Troubleshooting
1. Run: `./docker-manager.sh status`
2. If issues, run: `./docker-manager.sh logs`
3. For fresh start: `./docker-manager.sh rebuild`

### Emergency Reset
1. Run: `./docker-manager.sh cleanup`
2. Confirm with 'y'
3. Run: `./docker-manager.sh start`

## 📁 Key Files

- `docker-manager.sh` - Main management script (macOS/Linux)
- `docker-manager.bat` - Main management script (Windows)
- `.env` - Configuration file
- `docker-compose.dev.yml` - Development configuration
- `docker-compose.yml` - Production configuration

## 🆘 Need Help?

1. **Check Status**: `./docker-manager.sh status`
2. **View Logs**: `./docker-manager.sh logs`
3. **Restart**: `./docker-manager.sh restart`
4. **Full Help**: `./docker-manager.sh help`

---

*For detailed documentation, see README.md or DOCKER_QUICK_START.md*
