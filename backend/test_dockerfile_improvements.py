"""
Test file for Dockerfile improvements
Demonstrates and validates the enhanced Docker configuration
"""

import pytest
import subprocess
import json
import os
from pathlib import Path

def test_dockerfile_structure():
    """Test the structure and content of the improved Dockerfile"""
    print("\n" + "="*60)
    print("🐳 DOCKERFILE STRUCTURE TEST")
    print("="*60)
    
    dockerfile_path = Path("backend/Dockerfile")
    assert dockerfile_path.exists(), "Dockerfile should exist"
    
    content = dockerfile_path.read_text()
    
    # Test security improvements
    assert "groupadd --gid 1000 appuser" in content, "Should create non-root user"
    assert "USER appuser" in content, "Should switch to non-root user"
    assert "--chown=appuser:appuser" in content, "Should set proper file ownership"
    
    # Test optimization features
    assert "PYTHONUNBUFFERED=1" in content, "Should disable Python buffering"
    assert "PYTHONDONTWRITEBYTECODE=1" in content, "Should disable bytecode writing"
    assert "--mount=type=cache" in content, "Should use build cache"
    
    # Test health check
    assert "HEALTHCHECK" in content, "Should include health check"
    assert "/health" in content, "Should check health endpoint"
    
    # Test proper labeling
    assert "LABEL maintainer" in content, "Should include maintainer label"
    assert "org.opencontainers.image" in content, "Should include OCI labels"
    
    print("✅ Dockerfile structure validation passed")

def test_optimized_dockerfile_structure():
    """Test the multi-stage optimized Dockerfile"""
    print("\n=== Testing Optimized Dockerfile ===")
    
    dockerfile_path = Path("backend/Dockerfile.optimized")
    assert dockerfile_path.exists(), "Optimized Dockerfile should exist"
    
    content = dockerfile_path.read_text()
    
    # Test multi-stage build
    assert "FROM python:3.13-slim as builder" in content, "Should have builder stage"
    assert "FROM python:3.13-slim as production" in content, "Should have production stage"
    assert "FROM production as development" in content, "Should have development stage"
    
    # Test virtual environment usage
    assert "python -m venv /opt/venv" in content, "Should create virtual environment"
    assert "COPY --from=builder /opt/venv" in content, "Should copy virtual environment"
    
    # Test build optimizations
    assert "python -m compileall" in content, "Should pre-compile Python files"
    assert "tini" in content, "Should use tini as init system"
    
    # Test spaCy model verification
    assert "spacy.load('en_core_web_lg')" in content, "Should verify spaCy model"
    assert "en_core_web_sm" in content, "Should have fallback model"
    
    print("✅ Optimized Dockerfile structure validation passed")

def test_dockerignore_file():
    """Test .dockerignore file for build optimization"""
    print("\n=== Testing .dockerignore File ===")
    
    dockerignore_path = Path("backend/.dockerignore")
    assert dockerignore_path.exists(), ".dockerignore should exist"
    
    content = dockerignore_path.read_text()
    
    # Test essential exclusions
    essential_patterns = [
        "__pycache__",
        "*.pyc",
        ".git/",
        "tests/",
        "*.md",
        ".env",
        "Dockerfile.*",
        ".pytest_cache",
        "node_modules/",
        "*.log"
    ]
    
    for pattern in essential_patterns:
        assert pattern in content, f"Should exclude {pattern}"
    
    print("✅ .dockerignore validation passed")

def test_docker_compose_configurations():
    """Test Docker Compose configurations"""
    print("\n=== Testing Docker Compose Configurations ===")
    
    # Test production compose file
    prod_compose_path = Path("backend/docker-compose.prod.yml")
    assert prod_compose_path.exists(), "Production compose file should exist"
    
    prod_content = prod_compose_path.read_text()
    
    # Test production features
    assert "target: production" in prod_content, "Should target production stage"
    assert "restart: unless-stopped" in prod_content, "Should have restart policy"
    assert "FASTAPI_ENV=production" in prod_content, "Should set production environment"
    assert "healthcheck:" in prod_content, "Should include health checks"
    assert "networks:" in prod_content, "Should define networks"
    assert "volumes:" in prod_content, "Should define volumes"
    
    # Test development compose file
    dev_compose_path = Path("backend/docker-compose.dev.yml")
    assert dev_compose_path.exists(), "Development compose file should exist"
    
    dev_content = dev_compose_path.read_text()
    
    # Test development features
    assert "target: development" in dev_content, "Should target development stage"
    assert "FASTAPI_ENV=development" in dev_content, "Should set development environment"
    assert "RELOAD=true" in dev_content, "Should enable hot reload"
    assert "pgadmin:" in dev_content, "Should include pgAdmin"
    assert "redis-commander:" in dev_content, "Should include Redis Commander"
    assert "mailhog:" in dev_content, "Should include MailHog"
    assert "5678:5678" in dev_content, "Should expose debug port"
    
    print("✅ Docker Compose configurations validation passed")

def test_environment_variables():
    """Test environment variable handling"""
    print("\n=== Testing Environment Variables ===")
    
    compose_files = [
        "backend/docker-compose.prod.yml",
        "backend/docker-compose.dev.yml"
    ]
    
    for compose_file in compose_files:
        content = Path(compose_file).read_text()
        
        # Test essential environment variables
        essential_vars = [
            "FASTAPI_ENV",
            "LOG_LEVEL",
            "DB_URL",
            "SECRET_KEY",
            "JWT_SECRET"
        ]
        
        for var in essential_vars:
            assert var in content, f"Should define {var} in {compose_file}"
        
        print(f"✅ Environment variables validated for {compose_file}")

def test_security_features():
    """Test security-related configurations"""
    print("\n=== Testing Security Features ===")
    
    dockerfile_path = Path("backend/Dockerfile")
    content = dockerfile_path.read_text()
    
    # Test security measures
    security_features = [
        ("Non-root user", "USER appuser"),
        ("Proper ownership", "--chown=appuser:appuser"),
        ("Security updates", "apt-get update"),
        ("Clean package cache", "rm -rf /var/lib/apt/lists/*"),
        ("Minimal base image", "python:3.13-slim"),
        ("Proper permissions", "chmod +x"),
    ]
    
    for feature_name, pattern in security_features:
        assert pattern in content, f"Should include {feature_name}: {pattern}"
        print(f"✅ {feature_name} implemented")

def test_performance_optimizations():
    """Test performance optimization features"""
    print("\n=== Testing Performance Optimizations ===")
    
    optimized_dockerfile_path = Path("backend/Dockerfile.optimized")
    content = optimized_dockerfile_path.read_text()
    
    # Test performance features
    performance_features = [
        ("Multi-stage build", "FROM python:3.13-slim as builder"),
        ("Virtual environment", "python -m venv /opt/venv"),
        ("Pre-compilation", "python -m compileall"),
        ("Build cache", "--mount=type=cache"),
        ("Init system", "tini"),
        ("Layer optimization", "COPY --from=builder"),
    ]
    
    for feature_name, pattern in performance_features:
        assert pattern in content, f"Should include {feature_name}: {pattern}"
        print(f"✅ {feature_name} implemented")

def test_development_features():
    """Test development-specific features"""
    print("\n=== Testing Development Features ===")
    
    dev_compose_path = Path("backend/docker-compose.dev.yml")
    content = dev_compose_path.read_text()
    
    # Test development tools
    dev_tools = [
        ("pgAdmin", "dpage/pgadmin4"),
        ("Redis Commander", "rediscommander/redis-commander"),
        ("MailHog", "mailhog/mailhog"),
        ("Debug port", "5678:5678"),
        ("Hot reload", "RELOAD=true"),
        ("Verbose logging", "LOG_LEVEL=debug"),
    ]
    
    for tool_name, pattern in dev_tools:
        assert pattern in content, f"Should include {tool_name}: {pattern}"
        print(f"✅ {tool_name} configured")

def test_build_optimization():
    """Test build optimization strategies"""
    print("\n=== Testing Build Optimization ===")
    
    dockerfile_path = Path("backend/Dockerfile")
    content = dockerfile_path.read_text()
    
    # Test layer optimization
    optimization_features = [
        ("Requirements first", "COPY requirements.txt ."),
        ("Cache mount", "--mount=type=cache"),
        ("No cache pip", "--no-cache-dir"),
        ("Clean apt cache", "rm -rf /var/lib/apt/lists/*"),
        ("Minimal packages", "--no-install-recommends"),
    ]
    
    for feature_name, pattern in optimization_features:
        assert pattern in content, f"Should include {feature_name}: {pattern}"
        print(f"✅ {feature_name} implemented")

def test_monitoring_and_health():
    """Test monitoring and health check configurations"""
    print("\n=== Testing Monitoring and Health ===")
    
    # Test Dockerfile health checks
    dockerfile_path = Path("backend/Dockerfile")
    content = dockerfile_path.read_text()
    
    assert "HEALTHCHECK" in content, "Should include health check"
    assert "--interval=" in content, "Should specify check interval"
    assert "--timeout=" in content, "Should specify timeout"
    assert "--retries=" in content, "Should specify retry count"
    
    # Test compose health checks
    compose_files = [
        "backend/docker-compose.prod.yml",
        "backend/docker-compose.dev.yml"
    ]
    
    for compose_file in compose_files:
        content = Path(compose_file).read_text()
        assert "healthcheck:" in content, f"Should include health checks in {compose_file}"
        assert "condition: service_healthy" in content, f"Should wait for healthy services in {compose_file}"
    
    print("✅ Monitoring and health configurations validated")

def run_dockerfile_improvements_demo():
    """Run a comprehensive demo of Dockerfile improvements"""
    print("\n" + "="*60)
    print("🐳 DOCKERFILE IMPROVEMENTS DEMO")
    print("="*60)
    
    # Run all improvement tests
    test_dockerfile_structure()
    test_optimized_dockerfile_structure()
    test_dockerignore_file()
    test_docker_compose_configurations()
    test_environment_variables()
    test_security_features()
    test_performance_optimizations()
    test_development_features()
    test_build_optimization()
    test_monitoring_and_health()
    
    print("\n" + "="*60)
    print("✅ All Dockerfile improvement tests completed!")
    print("="*60)
    
    print("\n📋 DOCKERFILE IMPROVEMENTS SUMMARY:")
    print("• Enhanced security with non-root user")
    print("• Multi-stage builds for optimization")
    print("• Comprehensive .dockerignore for faster builds")
    print("• Production and development configurations")
    print("• Health checks and monitoring")
    print("• Build caching and layer optimization")
    print("• Development tools integration")
    print("• Proper environment variable handling")
    print("• Container labeling and metadata")
    print("• Signal handling with tini")
    
    print("\n🚀 NEW FILES CREATED:")
    print("• backend/Dockerfile (enhanced)")
    print("• backend/Dockerfile.optimized (multi-stage)")
    print("• backend/.dockerignore (comprehensive)")
    print("• backend/docker-compose.prod.yml (production)")
    print("• backend/docker-compose.dev.yml (development)")
    print("• backend/test_dockerfile_improvements.py (test suite)")
    
    print("\n🔧 KEY IMPROVEMENTS:")
    print("• Security: Non-root user, proper permissions")
    print("• Performance: Multi-stage builds, caching, pre-compilation")
    print("• Development: Hot reload, debug tools, admin interfaces")
    print("• Production: Optimized images, health checks, monitoring")
    print("• Maintainability: Clear separation of concerns")
    print("• Observability: Logging, health checks, metrics")
    
    print("\n📦 BUILD COMMANDS:")
    print("# Production build:")
    print("docker-compose -f docker-compose.prod.yml up --build")
    print()
    print("# Development build:")
    print("docker-compose -f docker-compose.dev.yml up --build")
    print()
    print("# Optimized multi-stage build:")
    print("docker build -f Dockerfile.optimized --target production -t travel-mvp:prod .")
    print("docker build -f Dockerfile.optimized --target development -t travel-mvp:dev .")
    
    print("\n🌐 DEVELOPMENT SERVICES:")
    print("• Backend API: http://localhost:8000")
    print("• pgAdmin: http://localhost:5050 (admin@travel-mvp.dev / admin123)")
    print("• Redis Commander: http://localhost:8081")
    print("• MailHog: http://localhost:8025")
    print("• PostgreSQL: localhost:5433")
    print("• Redis: localhost:6380")

if __name__ == "__main__":
    run_dockerfile_improvements_demo()