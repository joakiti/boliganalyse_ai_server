-- Migration to move apartment_listings table to private schema and create public view
-- Create the private schema if it doesn't exist
CREATE SCHEMA IF NOT EXISTS private;

-- Move the apartment_listings table to the private schema
ALTER TABLE public.apartment_listings 
  SET SCHEMA private;

-- Create the view in public schema referencing the table in its new location
CREATE OR REPLACE VIEW public.client_apartment_listings AS
SELECT id, url, property_image_url, analysis, created_at, updated_at, status
FROM private.apartment_listings;

-- Revoke access to the private schema from regular users
REVOKE ALL ON SCHEMA private FROM anon, authenticated;
REVOKE ALL ON ALL TABLES IN SCHEMA private FROM anon, authenticated;

-- Ensure the public view is accessible
GRANT SELECT ON public.client_apartment_listings TO anon, authenticated;

-- Grant USAGE permission on the private schema to service_role
GRANT USAGE ON SCHEMA private TO service_role;

-- Grant ALL permissions on all tables in the private schema to service_role
GRANT ALL ON ALL TABLES IN SCHEMA private TO service_role;

-- Also grant permissions on future tables that might be created in this schema
ALTER DEFAULT PRIVILEGES IN SCHEMA private
GRANT ALL ON TABLES TO service_role;

