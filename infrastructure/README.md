# 🐳 Travel MVP Docker Infrastructure

This directory contains the Docker Compose configuration for the Travel MVP project.

## 📁 Files Overview

- **`docker-compose.yml`** - Base configuration (database, redis, backend)
- **`docker-compose.override.yml`** - Development overrides (automatically applied)
- **`docker-compose.prod.yml`** - Production overrides

## 🚀 Usage

### Development (Default)
```bash
# From the infrastructure directory
docker-compose up --build

# Or from project root
docker-compose -f infrastructure/docker-compose.yml up --build
```

The override file is automatically applied, giving you:
- Hot reload enabled
- Debug logging
- Development tools (pgAdmin, Redis Commander)
- Debug port exposed (5678)

### Production
```bash
# From the infrastructure directory
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up --build

# Or from project root
docker-compose -f infrastructure/docker-compose.yml -f infrastructure/docker-compose.prod.yml up --build
```

Production configuration includes:
- Optimized database settings
- Multiple workers (4)
- Production logging
- Rate limiting enabled
- Optional Nginx reverse proxy

## 🌐 Service Endpoints

### Development
- **Backend API**: http://localhost:8000
- **pgAdmin**: http://localhost:5050 (admin@travel-mvp.dev / admin123)
- **Redis Commander**: http://localhost:8081
- **PostgreSQL**: localhost:5432
- **Redis**: localhost:6379

### Production
- **Backend API**: http://localhost:8000 (or through Nginx)
- **PostgreSQL**: localhost:5432 (internal)
- **Redis**: localhost:6379 (internal)
- **Nginx**: http://localhost:80, https://localhost:443

## 🔧 Environment Variables

Create a `.env` file in the project root with:

```env
# Database
POSTGRES_PASSWORD=your_secure_password

# Security
SECRET_KEY=your_secret_key
JWT_SECRET=your_jwt_secret
JWT_REFRESH_SECRET=your_jwt_refresh_secret

# Optional: External APIs
OPENAI_API_KEY=your_openai_api_key
GOOGLE_MAPS_API_KEY=your_google_maps_api_key

# Production settings
FASTAPI_ENV=production  # For production
LOG_LEVEL=info          # For production
WORKERS=4               # For production
```

## 🏥 Health Checks

All services include health checks:
- **Backend**: `GET /health`
- **Database**: `pg_isready`
- **Redis**: `redis-cli ping`

## 📊 Volumes

Persistent storage:
- `postgres_data` - Database data
- `redis_data` - Redis cache data
- `backend_logs` - Application logs
- `backend_models` - ML models
- `backend_temp` - Temporary files
- `pgadmin_data` - pgAdmin configuration (dev only)

## 🔒 Security Features

- Non-root user execution
- Health checks and monitoring
- Secure environment variable handling
- Network isolation
- Proper restart policies

## 🛠️ Troubleshooting

### Reset everything
```bash
docker-compose down -v
docker-compose up --build
```

### View logs
```bash
docker-compose logs -f backend
docker-compose logs -f db
```

### Database shell
```bash
docker-compose exec db psql -U postgres -d traveldb
```

### Backend shell
```bash
docker-compose exec backend bash
```