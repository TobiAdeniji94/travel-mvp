# Quick Start: Infrastructure Optimization

## ✅ What's Already Done (Today)

- [x] Added Gunicorn to requirements
- [x] Updated start.sh with multi-worker support
- [x] Fixed frontend Dockerfile for Next.js 15
- [x] Enhanced .env.example with all variables
- [x] Created nginx configuration
- [x] Created implementation plan

## 🚀 Next Steps (15 Minutes)

### 1. Create Your .env File
```bash
cp .env.example .env
```

Edit `.env` and set:
```bash
FASTAPI_ENV=production
WORKERS=4
POSTGRES_PASSWORD=your_secure_password
SECRET_KEY=your_secret_key_here
JWT_SECRET=your_jwt_secret_here
JWT_REFRESH_SECRET=your_refresh_secret_here
```

### 2. Rebuild and Test
```bash
cd infrastructure
docker compose down -v
docker compose build --no-cache
docker compose up -d
```

### 3. Verify Multi-Worker is Running
```bash
# Should see "Starting production server with Gunicorn"
docker compose logs backend | grep -i gunicorn

# Should see 4+ worker processes
docker compose exec backend ps aux | grep gunicorn
```

### 4. Test Performance
```bash
# Health check
curl http://localhost:8000/health

# NLP endpoint
curl -X POST http://localhost:8000/api/v1/nlp/parse \
  -H "Content-Type: application/json" \
  -d '{"text":"Plan a 3-day trip to Paris with $2000 budget"}'
```

## 📋 Full Implementation Timeline

| Day | Task | Time | Status |
|-----|------|------|--------|
| 1 | Foundation setup | 2h | ✅ DONE |
| 2 | Test multi-worker | 2-3h | ⏳ NEXT |
| 3 | Add nginx proxy | 3-4h | 📅 PLANNED |
| 4-5 | Redis caching | 4-6h | 📅 PLANNED |
| 6 | Optimize Postgres | 2h | 📅 PLANNED |
| 7 | Production cleanup | 2h | 📅 PLANNED |

## 📚 Documentation

- **Full Plan:** `IMPLEMENTATION_PLAN.md` - Day-by-day instructions
- **Technical Details:** `INFRASTRUCTURE_OPTIMIZATION.md` - Deep dive
- **Nginx Config:** `infrastructure/nginx/nginx.conf` - Ready to use

## 🎯 Expected Results After Day 2

- ✅ 4+ Gunicorn workers running
- ✅ 400-800 req/s throughput (vs ~100 before)
- ✅ P95 latency < 200ms
- ✅ No 500 errors under load

## 🚨 If Something Goes Wrong

```bash
# Revert to single worker mode
# Edit .env:
FASTAPI_ENV=development
WORKERS=1

# Restart
docker compose restart backend
```

## 📞 Support

- Check `IMPLEMENTATION_PLAN.md` for troubleshooting guide
- Review logs: `docker compose logs backend`
- Check health: `curl http://localhost:8000/health`
