

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;


CREATE EXTENSION IF NOT EXISTS "pgsodium";






COMMENT ON SCHEMA "public" IS 'standard public schema';



CREATE EXTENSION IF NOT EXISTS "pg_graphql" WITH SCHEMA "graphql";






CREATE EXTENSION IF NOT EXISTS "pg_stat_statements" WITH SCHEMA "extensions";






CREATE EXTENSION IF NOT EXISTS "pgcrypto" WITH SCHEMA "extensions";






CREATE EXTENSION IF NOT EXISTS "pgjwt" WITH SCHEMA "extensions";






CREATE EXTENSION IF NOT EXISTS "supabase_vault" WITH SCHEMA "vault";






CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA "extensions";





SET default_tablespace = '';

SET default_table_access_method = "heap";


CREATE TABLE IF NOT EXISTS "public"."apartment_listings" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "url" "text" NOT NULL,
    "normalized_url" "text" NOT NULL,
    "html_content" "text",
    "status" "text" DEFAULT 'pending'::"text" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "analysis" "jsonb",
    "error_message" "text",
    "partial_analysis" "jsonb",
    "property_image_url" "text"
);


ALTER TABLE "public"."apartment_listings" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."feedback" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "feedback_type" "text" NOT NULL,
    "message" "text" NOT NULL,
    "email" "text",
    "property_id" "text",
    "property_address" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL
);


ALTER TABLE "public"."feedback" OWNER TO "postgres";


ALTER TABLE ONLY "public"."apartment_listings"
    ADD CONSTRAINT "apartment_listings_normalized_url_key" UNIQUE ("normalized_url");



ALTER TABLE ONLY "public"."apartment_listings"
    ADD CONSTRAINT "apartment_listings_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."apartment_listings"
    ADD CONSTRAINT "apartment_listings_url_key" UNIQUE ("url");



ALTER TABLE ONLY "public"."feedback"
    ADD CONSTRAINT "feedback_pkey" PRIMARY KEY ("id");



CREATE INDEX "apartment_listings_normalized_url_idx" ON "public"."apartment_listings" USING "btree" ("normalized_url");



CREATE INDEX "idx_apartment_listings_analysis" ON "public"."apartment_listings" USING "gin" ("analysis");



CREATE POLICY "Allow admins to manage feedback" ON "public"."feedback" USING (true);



CREATE POLICY "Allow anonymous access to apartment_listings" ON "public"."apartment_listings" TO "anon" USING (true);



CREATE POLICY "Allow anonymous insert" ON "public"."feedback" FOR INSERT TO "anon" WITH CHECK (true);



ALTER TABLE "public"."apartment_listings" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."feedback" ENABLE ROW LEVEL SECURITY;




ALTER PUBLICATION "supabase_realtime" OWNER TO "postgres";






ALTER PUBLICATION "supabase_realtime" ADD TABLE ONLY "public"."apartment_listings";



GRANT USAGE ON SCHEMA "public" TO "postgres";
GRANT USAGE ON SCHEMA "public" TO "anon";
GRANT USAGE ON SCHEMA "public" TO "authenticated";
GRANT USAGE ON SCHEMA "public" TO "service_role";



































































































































































































GRANT ALL ON TABLE "public"."apartment_listings" TO "anon";
GRANT ALL ON TABLE "public"."apartment_listings" TO "authenticated";
GRANT ALL ON TABLE "public"."apartment_listings" TO "service_role";



GRANT ALL ON TABLE "public"."feedback" TO "anon";
GRANT ALL ON TABLE "public"."feedback" TO "authenticated";
GRANT ALL ON TABLE "public"."feedback" TO "service_role";



ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES  TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES  TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES  TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES  TO "service_role";






ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS  TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS  TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS  TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS  TO "service_role";






ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES  TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES  TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES  TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES  TO "service_role";






























RESET ALL;
