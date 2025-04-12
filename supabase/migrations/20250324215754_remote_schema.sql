alter table "private"."apartment_listings" drop column "partial_analysis";

alter table "private"."apartment_listings" add column "html_url" text;

alter table "private"."apartment_listings" add column "html_url_redirect" text;

alter table "private"."apartment_listings" add column "realtor" text;

alter table "private"."apartment_listings" add column "url_redirect" text;

set check_function_bodies = off;

CREATE OR REPLACE FUNCTION private.extract_realtor_from_url(url text)
 RETURNS text
 LANGUAGE plpgsql
AS $function$
BEGIN
    RETURN regexp_replace(regexp_replace(url, 'https?://(?:www\.)?([^/]+).*', '\1'), '^(?:www\.)?(.+)', '\1');
END;
$function$
;

CREATE OR REPLACE FUNCTION private.set_realtor_trigger_function()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
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
$function$
;

CREATE TRIGGER set_realtor_trigger BEFORE INSERT OR UPDATE ON private.apartment_listings FOR EACH ROW EXECUTE FUNCTION private.set_realtor_trigger_function();


create or replace view "public"."client_apartment_listings" as  SELECT apartment_listings.id,
    apartment_listings.url,
    apartment_listings.property_image_url,
    apartment_listings.analysis,
    apartment_listings.created_at,
    apartment_listings.updated_at,
    apartment_listings.status,
    apartment_listings.realtor
   FROM private.apartment_listings;



