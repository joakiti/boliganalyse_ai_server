

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






CREATE SCHEMA IF NOT EXISTS "private";


ALTER SCHEMA "private" OWNER TO "postgres";


COMMENT ON SCHEMA "public" IS 'standard public schema';



CREATE EXTENSION IF NOT EXISTS "pg_graphql" WITH SCHEMA "graphql";






CREATE EXTENSION IF NOT EXISTS "pg_stat_statements" WITH SCHEMA "extensions";






CREATE EXTENSION IF NOT EXISTS "pgcrypto" WITH SCHEMA "extensions";






CREATE EXTENSION IF NOT EXISTS "pgjwt" WITH SCHEMA "extensions";






CREATE EXTENSION IF NOT EXISTS "supabase_vault" WITH SCHEMA "vault";






CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA "extensions";






CREATE OR REPLACE FUNCTION "private"."extract_realtor_from_url"("url" "text") RETURNS "text"
    LANGUAGE "plpgsql"
    AS $$
BEGIN
    RETURN regexp_replace(regexp_replace(url, 'https?://(?:www\.)?([^/]+).*', '\1'), '^(?:www\.)?(.+)', '\1');
END;
$$;


ALTER FUNCTION "private"."extract_realtor_from_url"("url" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "private"."set_realtor_trigger_function"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    AS $$
BEGIN
  -- Only set realtor if it's NULL or URL has changed
  IF NEW.realtor IS NULL OR OLD.url <> NEW.url THEN
    IF NEW.url_redirect IS NOT NULL THEN
      NEW.realtor := private.extract_realtor_from_url(NEW.url_redirect);
    ELSE
      NEW.realtor := private.extract_realtor_from_url(NEW.url);
    END IF;
  END IF;
  RETURN NEW;
END;
$$;


ALTER FUNCTION "private"."set_realtor_trigger_function"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."handle_new_listing"() RETURNS "trigger"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO ''
    AS $$
begin
  insert into public.client_apartment_listings (id, url, property_image_url, analysis, created_at, updated_at, status, realtor)
  VALUES (NEW.id, NEW.url, NEW.property_image_url, NEW.analysis, NEW.created_at, NEW.updated_at, NEW.status, NEW.realtor);
  return new;
end;
$$;


ALTER FUNCTION "public"."handle_new_listing"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."handle_update_listing"() RETURNS "trigger"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO ''
    AS $$
BEGIN
    UPDATE public.client_apartment_listings
    SET 
        url = NEW.url,
        property_image_url = NEW.property_image_url,
        analysis = NEW.analysis,
        updated_at = now(),
        status = NEW.status,
        realtor = NEW.realtor
    WHERE id = NEW.id;

    RETURN NEW;
END;
$$;


ALTER FUNCTION "public"."handle_update_listing"() OWNER TO "postgres";

SET default_tablespace = '';

SET default_table_access_method = "heap";


CREATE TABLE IF NOT EXISTS "private"."apartment_listings" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "url" "text" NOT NULL,
    "normalized_url" "text" NOT NULL,
    "html_content" "text",
    "status" "text" DEFAULT 'pending'::"text" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "analysis" "jsonb",
    "error_message" "text",
    "property_image_url" "text",
    "realtor" "text",
    "url_redirect" "text",
    "html_url" "text",
    "html_url_redirect" "text",
    "text_extracted" "text",
    "text_extracted_redirect" "text"
);


ALTER TABLE "private"."apartment_listings" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."client_apartment_listings" (
    "id" "uuid" NOT NULL,
    "url" "text",
    "property_image_url" "text",
    "analysis" "jsonb",
    "created_at" timestamp with time zone DEFAULT "now"(),
    "updated_at" timestamp with time zone DEFAULT "now"(),
    "status" "text",
    "realtor" "text"
);


ALTER TABLE "public"."client_apartment_listings" OWNER TO "postgres";


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


ALTER TABLE ONLY "private"."apartment_listings"
    ADD CONSTRAINT "apartment_listings_normalized_url_key" UNIQUE ("normalized_url");



ALTER TABLE ONLY "private"."apartment_listings"
    ADD CONSTRAINT "apartment_listings_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "private"."apartment_listings"
    ADD CONSTRAINT "apartment_listings_url_key" UNIQUE ("url");



ALTER TABLE ONLY "public"."client_apartment_listings"
    ADD CONSTRAINT "client_apartment_listings_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."feedback"
    ADD CONSTRAINT "feedback_pkey" PRIMARY KEY ("id");



CREATE INDEX "apartment_listings_normalized_url_idx" ON "private"."apartment_listings" USING "btree" ("normalized_url");



CREATE INDEX "idx_apartment_listings_analysis" ON "private"."apartment_listings" USING "gin" ("analysis");



CREATE OR REPLACE TRIGGER "on_new_analysis" AFTER INSERT ON "private"."apartment_listings" FOR EACH ROW EXECUTE FUNCTION "public"."handle_new_listing"();



CREATE OR REPLACE TRIGGER "on_update_analysis" AFTER UPDATE ON "private"."apartment_listings" FOR EACH ROW EXECUTE FUNCTION "public"."handle_update_listing"();



CREATE OR REPLACE TRIGGER "set_realtor_trigger" BEFORE INSERT OR UPDATE ON "private"."apartment_listings" FOR EACH ROW EXECUTE FUNCTION "private"."set_realtor_trigger_function"();



ALTER TABLE ONLY "public"."client_apartment_listings"
    ADD CONSTRAINT "client_apartment_listings_id_fkey" FOREIGN KEY ("id") REFERENCES "private"."apartment_listings"("id");



ALTER TABLE "private"."apartment_listings" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "Allow anonymous insert" ON "public"."feedback" FOR INSERT TO "anon" WITH CHECK (true);



CREATE POLICY "Enable read access for all users" ON "public"."client_apartment_listings" FOR SELECT USING (true);



ALTER TABLE "public"."client_apartment_listings" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."feedback" ENABLE ROW LEVEL SECURITY;




ALTER PUBLICATION "supabase_realtime" OWNER TO "postgres";






ALTER PUBLICATION "supabase_realtime" ADD TABLE ONLY "private"."apartment_listings";



ALTER PUBLICATION "supabase_realtime" ADD TABLE ONLY "public"."client_apartment_listings";



GRANT USAGE ON SCHEMA "private" TO "service_role";



GRANT USAGE ON SCHEMA "public" TO "postgres";
GRANT USAGE ON SCHEMA "public" TO "anon";
GRANT USAGE ON SCHEMA "public" TO "authenticated";
GRANT USAGE ON SCHEMA "public" TO "service_role";




















































































































































































REVOKE ALL ON FUNCTION "private"."extract_realtor_from_url"("url" "text") FROM PUBLIC;
GRANT ALL ON FUNCTION "private"."extract_realtor_from_url"("url" "text") TO "service_role";



REVOKE ALL ON FUNCTION "private"."set_realtor_trigger_function"() FROM PUBLIC;
GRANT ALL ON FUNCTION "private"."set_realtor_trigger_function"() TO "service_role";



REVOKE ALL ON FUNCTION "public"."handle_new_listing"() FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."handle_new_listing"() TO "service_role";



REVOKE ALL ON FUNCTION "public"."handle_update_listing"() FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."handle_update_listing"() TO "service_role";


















GRANT ALL ON TABLE "private"."apartment_listings" TO "service_role";



GRANT ALL ON TABLE "public"."client_apartment_listings" TO "anon";
GRANT ALL ON TABLE "public"."client_apartment_listings" TO "authenticated";
GRANT ALL ON TABLE "public"."client_apartment_listings" TO "service_role";



GRANT ALL ON TABLE "public"."feedback" TO "anon";
GRANT ALL ON TABLE "public"."feedback" TO "authenticated";
GRANT ALL ON TABLE "public"."feedback" TO "service_role";



ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "private" GRANT ALL ON TABLES  TO "service_role";



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
