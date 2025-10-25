# Infrastructure Optimization - Implementation Plan

## 📅 **Execution Timeline**

---

## ✅ **Day 1: Foundation (COMPLETED - 2 hours)**

### What We Just Did:
- [x] Added Gunicorn to `backend/requirements/app.txt`
- [x] Updated `backend/start.sh` with production-ready multi-worker support
- [x] Enhanced `.env.example` with all required variables
- [x] Fixed `frontend/Dockerfile` for Next.js 15 compatibility

### Validation Steps:
```bash
# 1. Verify Gunicorn is in requirements
grep "gunicorn" backend/requirements/app.txt

# 2. Check start script has multi-worker logic
grep "WORKERS" backend/start.sh

# 3. Verify frontend Dockerfile uses .next directory
grep ".next" frontend/Dockerfile
```

**Status:** ✅ **READY TO TEST**

---

## 🚀 **Day 2: Test & Deploy Multi-Worker Setup (2-3 hours)**

### Step 1: Create Your .env File
```bash
# Copy example and customize
cp .env.example .env

# Edit .env with your values:
# - Set FASTAPI_ENV=production for testing
# - Set WORKERS=4 (or 2x your CPU cores)
# - Update POSTGRES_PASSWORD
# - Update SECRET_KEY and JWT secrets
```

### Step 2: Rebuild Everything
```bash
cd infrastructure

# Clean slate
docker compose down -v

# Rebuild with new dependencies
docker compose build --no-cache

# Start services
docker compose up -d

# Watch logs
docker compose logs -f backend
```

### Step 3: Verify Multi-Worker is Running
```bash
# Check backend logs - should see "Starting production server with Gunicorn"
docker compose logs backend | grep "Gunicorn"

# Check process count (should see 4+ workers)
docker compose exec backend ps aux | grep gunicorn

# Expected output:
# appuser    1  gunicorn: master [app.main:app]
# appuser   10  gunicorn: worker [app.main:app]
# appuser   11  gunicorn: worker [app.main:app]
# appuser   12  gunicorn: worker [app.main:app]
# appuser   13  gunicorn: worker [app.main:app]
```

### Step 4: Performance Baseline Test
```bash
# Install Apache Bench (if not installed)
# Windows: Download from https://www.apachelounge.com/download/
# Mac: brew install apache-bench
# Linux: sudo apt-get install apache2-utils

# Test health endpoint (light)
ab -n 1000 -c 10 http://localhost:8000/health

# Test NLP endpoint (heavy)
ab -n 100 -c 5 -p test-request.json -T application/json http://localhost:8000/api/v1/nlp/parse

# Create test-request.json:
echo '{"text":"Plan a 3-day trip to Paris with $2000 budget"}' > test-request.json
```

### Step 5: Record Metrics
```bash
# Document these metrics for comparison:
# - Requests per second
# - Mean response time
# - P95 latency
# - Failed requests (should be 0)
```

**Expected Results:**
- ✅ 4+ Gunicorn workers running
- ✅ 400-800 req/s on /health endpoint
- ✅ 20-50 req/s on /nlp/parse endpoint
- ✅ P95 latency < 200ms for health checks
- ✅ No 500 errors

**Rollback Plan:**
```bash
# If issues occur, revert to single worker:
# In .env:
FASTAPI_ENV=development
WORKERS=1

# Restart:
docker compose restart backend
```

---

## 📦 **Day 3: Add Nginx Reverse Proxy (3-4 hours)**

### Step 1: Add Nginx Service to docker-compose.yml

Edit `infrastructure/docker-compose.yml` and add after the frontend service:

```yaml
  # Nginx Reverse Proxy
  nginx:
    image: nginx:alpine
    container_name: travel-mvp-nginx
    restart: unless-stopped
    ports:
      - "80:80"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/conf.d/default.conf:ro
      - nginx_cache:/var/cache/nginx
      - nginx_logs:/var/log/nginx
    depends_on:
      - backend
      - frontend
    networks:
      - travel-mvp-network
    healthcheck:
      test: ["CMD", "wget", "--quiet", "--tries=1", "--spider", "http://localhost/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

Add to volumes section:
```yaml
volumes:
  nginx_cache:
    driver: local
  nginx_logs:
    driver: local
```

### Step 2: Update Port Mappings

Remove port mappings from backend and frontend (nginx will handle):
```yaml
# backend: - Remove "8000:8000"
# frontend: - Remove "3000:3000"
```

### Step 3: Test Nginx Configuration

```bash
# Restart with nginx
docker compose up -d

# Check nginx is running
docker compose ps nginx

# Test through nginx (port 80)
curl http://localhost/health
curl http://localhost/api/v1/security/health

# Check nginx logs
docker compose logs nginx
```

### Step 4: Verify Rate Limiting

```bash
# Test rate limiting on auth endpoint (5 req/min limit)
for i in {1..10}; do
  curl -X POST http://localhost/api/v1/auth/login \
    -H "Content-Type: application/json" \
    -d '{"username":"test","password":"test"}' \
    -w "\\nStatus: %{http_code}\\n"
  sleep 1
done

# Should see 429 (Too Many Requests) after 5 requests
```

**Expected Results:**
- ✅ Nginx running on port 80
- ✅ Backend/frontend accessible through nginx
- ✅ Rate limiting working (429 errors after threshold)
- ✅ Health checks passing

---

## 🔄 **Day 4-5: Redis Caching Implementation (4-6 hours)**

### Step 1: Create Cache Module

Create `backend/app/core/cache.py`:

```python
import redis.asyncio as redis
from functools import wraps
import json
import hashlib
import logging
from typing import Optional, Any, Callable

logger = logging.getLogger(__name__)

# Redis client (initialized on startup)
redis_client: Optional[redis.Redis] = None

async def init_redis(url: str = "redis://redis:6379"):
    """Initialize Redis connection"""
    global redis_client
    try:
        redis_client = redis.from_url(url, decode_responses=True)
        await redis_client.ping()
        logger.info("✅ Redis connection established")
    except Exception as e:
        logger.error(f"❌ Redis connection failed: {e}")
        redis_client = None

async def close_redis():
    """Close Redis connection"""
    global redis_client
    if redis_client:
        await redis_client.close()
        logger.info("Redis connection closed")

def cache_result(ttl: int = 300, key_prefix: str = ""):
    """
    Cache decorator for expensive operations
    
    Args:
        ttl: Time to live in seconds (default 5 minutes)
        key_prefix: Optional prefix for cache key
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            if not redis_client:
                # Redis not available, execute function directly
                return await func(*args, **kwargs)
            
            try:
                # Generate cache key from function name and arguments
                args_str = str(args) + str(sorted(kwargs.items()))
                key_hash = hashlib.md5(args_str.encode()).hexdigest()
                cache_key = f"{key_prefix}{func.__name__}:{key_hash}"
                
                # Try to get from cache
                cached = await redis_client.get(cache_key)
                if cached:
                    logger.debug(f"Cache HIT: {cache_key}")
                    return json.loads(cached)
                
                # Cache miss - execute function
                logger.debug(f"Cache MISS: {cache_key}")
                result = await func(*args, **kwargs)
                
                # Store in cache
                await redis_client.setex(
                    cache_key,
                    ttl,
                    json.dumps(result, default=str)
                )
                
                return result
                
            except Exception as e:
                logger.error(f"Cache error: {e}")
                # On cache error, execute function directly
                return await func(*args, **kwargs)
        
        return wrapper
    return decorator
```

### Step 2: Initialize Redis in main.py

Update `backend/app/main.py`:

```python
from app.core.cache import init_redis, close_redis

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting application...")
    try:
        logger.info("Initializing database manager...")
        await db_manager.initialize()
        logger.info("Database manager initialized successfully")
        
        # Initialize Redis
        logger.info("Initializing Redis cache...")
        await init_redis()
        
    except Exception as e:
        logger.exception("Failed to initialize services")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down application...")
    try:
        await db_manager.close()
        await close_redis()
        logger.info("Services closed successfully")
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
```

### Step 3: Add Caching to Expensive Operations

Update `backend/app/api/itinerary.py`:

```python
from app.core.cache import cache_result

@cache_result(ttl=3600, key_prefix="dest:")  # Cache for 1 hour
async def get_destination_ids(interests: List[str], budget: Optional[float]):
    """Get destination recommendations using ML models (CACHED)"""
    if not ML_MODELS:
        raise HTTPException(status_code=500, detail="ML models not available")
    
    # ... existing code ...

@cache_result(ttl=3600, key_prefix="act:")
async def get_activity_ids(interests: List[str], budget: Optional[float]):
    """Get activity recommendations using ML models (CACHED)"""
    # ... existing code ...

@cache_result(ttl=3600, key_prefix="acc:")
async def get_accommodation_ids(interests: List[str], budget: Optional[float]):
    """Get accommodation recommendations using ML models (CACHED)"""
    # ... existing code ...
```

### Step 4: Add Redis Dependency

Update `backend/requirements/app.txt`:
```bash
echo "redis==5.0.1" >> backend/requirements/app.txt
```

### Step 5: Test Caching

```bash
# Rebuild and restart
docker compose build backend
docker compose restart backend

# Test cache performance
time curl -X POST http://localhost/api/v1/nlp/parse \
  -H "Content-Type: application/json" \
  -d '{"text":"Plan a trip to Paris"}'

# Run again (should be much faster from cache)
time curl -X POST http://localhost/api/v1/nlp/parse \
  -H "Content-Type: application/json" \
  -d '{"text":"Plan a trip to Paris"}'

# Check Redis keys
docker compose exec redis redis-cli KEYS "*"
docker compose exec redis redis-cli GET "nlp:parse:..."
```

**Expected Results:**
- ✅ First request: 100-500ms
- ✅ Cached request: <10ms
- ✅ Redis keys visible in redis-cli
- ✅ Cache TTL working (keys expire)

---

## 🗄️ **Day 6: Optimize Postgres Configuration (2 hours)**

### Step 1: Update docker-compose.yml

Replace the postgres command section:

```yaml
  db:
    command: >
      postgres
      -c shared_preload_libraries=pg_stat_statements
      -c max_connections=100
      -c shared_buffers=512MB
      -c effective_cache_size=2GB
      -c maintenance_work_mem=128MB
      -c checkpoint_completion_target=0.9
      -c wal_buffers=16MB
      -c default_statistics_target=100
      -c random_page_cost=1.1
      -c effective_io_concurrency=200
      -c work_mem=5MB
      -c min_wal_size=1GB
      -c max_wal_size=4GB
      -c max_worker_processes=4
      -c max_parallel_workers_per_gather=2
      -c max_parallel_workers=4
```

### Step 2: Restart Database

```bash
docker compose restart db

# Wait for health check
docker compose ps db

# Verify settings
docker compose exec db psql -U postgres -d traveldb -c "SHOW shared_buffers;"
docker compose exec db psql -U postgres -d traveldb -c "SHOW effective_cache_size;"
```

### Step 3: Test Query Performance

```bash
# Enable query timing
docker compose exec db psql -U postgres -d traveldb

# In psql:
\\timing on
SELECT COUNT(*) FROM activities;
SELECT * FROM activities WHERE latitude BETWEEN 40 AND 41 LIMIT 10;
```

**Expected Results:**
- ✅ Queries 2-3x faster
- ✅ Better connection pooling
- ✅ No connection errors under load

---

## 🧹 **Day 7: Production Cleanup (2 hours)**

### Step 1: Remove Dev Volume Mounts

Update `infrastructure/docker-compose.yml`:

```yaml
  backend:
    # REMOVE this line:
    # volumes:
    #   - ../backend:/app
    
    # KEEP only these:
    volumes:
      - backend_logs:/app/logs
      - backend_models:/app/models
      - backend_temp:/app/temp
```

### Step 2: Create Production Compose File

The file `infrastructure/docker-compose.prod.yml` already exists. Review and update if needed.

### Step 3: Test Production Mode

```bash
# Use production compose
docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d

# Verify no source code mounts
docker compose exec backend ls -la /app
# Should NOT see __pycache__ or .git

# Test hot reload is disabled
# Edit a Python file - changes should NOT appear without rebuild
```

### Step 4: Document Deployment Process

Create `infrastructure/DEPLOYMENT.md` with production deployment steps.

---

## 📊 **Week 2: High Impact Optimizations**

### Day 8-9: Monitoring Setup (Optional but Recommended)

1. Add Prometheus for metrics
2. Add Grafana for dashboards
3. Configure alerts

### Day 10-12: Load Testing & Tuning

1. Run comprehensive load tests
2. Identify bottlenecks
3. Fine-tune worker counts and cache TTLs
4. Document optimal settings

---

## 🎯 **Success Criteria**

After completing this plan, you should have:

- [x] ✅ Multi-worker backend (4+ workers)
- [x] ✅ Nginx reverse proxy with rate limiting
- [x] ✅ Redis caching for expensive operations
- [x] ✅ Optimized Postgres configuration
- [x] ✅ Production-ready Docker setup
- [ ] 📊 8-10x performance improvement
- [ ] 📊 <200ms P95 latency
- [ ] 📊 800+ req/s throughput

---

## 🚨 **Troubleshooting Guide**

### Issue: Gunicorn workers crashing
```bash
# Check memory usage
docker stats

# Reduce workers if needed
WORKERS=2

# Check logs for OOM errors
docker compose logs backend | grep -i "killed"
```

### Issue: Redis connection errors
```bash
# Check Redis is running
docker compose ps redis

# Test connection
docker compose exec backend python -c "import redis; r=redis.from_url('redis://redis:6379'); print(r.ping())"
```

### Issue: Nginx 502 Bad Gateway
```bash
# Check backend is healthy
docker compose ps backend
curl http://localhost:8000/health

# Check nginx logs
docker compose logs nginx

# Verify network connectivity
docker compose exec nginx ping backend
```

### Issue: Slow database queries
```bash
# Check connection pool
docker compose exec db psql -U postgres -d traveldb -c "SELECT count(*) FROM pg_stat_activity;"

# Check slow queries
docker compose exec db psql -U postgres -d traveldb -c "SELECT query, mean_exec_time FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 10;"
```

---

## 📞 **Next Steps**

1. **Today:** Copy `.env.example` to `.env` and customize
2. **Tomorrow:** Run Day 2 tests and verify multi-worker setup
3. **This Week:** Complete Days 3-7
4. **Next Week:** Monitoring and load testing

**Questions or issues?** Check the troubleshooting guide or review `INFRASTRUCTURE_OPTIMIZATION.md` for detailed explanations.

