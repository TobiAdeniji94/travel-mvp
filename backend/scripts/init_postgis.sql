-- Enable PostGIS extension for spatial queries
-- This script runs automatically when the database container starts

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;

-- Verify installation
SELECT PostGIS_Version();
