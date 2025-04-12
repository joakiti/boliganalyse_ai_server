drop policy "Allow anonymous access to apartment_listings" on "private"."apartment_listings";

CREATE TRIGGER on_new_analysis AFTER INSERT ON private.apartment_listings FOR EACH ROW EXECUTE FUNCTION handle_new_listing();

CREATE TRIGGER on_update_analysis AFTER UPDATE ON private.apartment_listings FOR EACH ROW EXECUTE FUNCTION handle_update_listing();


drop view if exists "public"."client_apartment_listings";

create table "public"."client_apartment_listings" (
    "id" uuid not null,
    "url" text,
    "property_image_url" text,
    "analysis" jsonb,
    "created_at" timestamp with time zone default now(),
    "updated_at" timestamp with time zone default now(),
    "status" text,
    "realtor" text
);


alter table "public"."client_apartment_listings" enable row level security;

CREATE UNIQUE INDEX client_apartment_listings_pkey ON public.client_apartment_listings USING btree (id);

alter table "public"."client_apartment_listings" add constraint "client_apartment_listings_pkey" PRIMARY KEY using index "client_apartment_listings_pkey";

alter table "public"."client_apartment_listings" add constraint "client_apartment_listings_id_fkey" FOREIGN KEY (id) REFERENCES private.apartment_listings(id) not valid;

alter table "public"."client_apartment_listings" validate constraint "client_apartment_listings_id_fkey";

set check_function_bodies = off;

CREATE OR REPLACE FUNCTION public.handle_new_listing()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
begin
  insert into public.client_apartment_listings (id, url, property_image_url, analysis, created_at, updated_at, status, realtor)
  VALUES (NEW.id, NEW.url, NEW.property_image_url, NEW.analysis, NEW.created_at, NEW.updated_at, NEW.status, NEW.realtor);
  return new;
end;
$function$
;

CREATE OR REPLACE FUNCTION public.handle_update_listing()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
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
$function$
;

grant delete on table "public"."client_apartment_listings" to "anon";

grant insert on table "public"."client_apartment_listings" to "anon";

grant references on table "public"."client_apartment_listings" to "anon";

grant select on table "public"."client_apartment_listings" to "anon";

grant trigger on table "public"."client_apartment_listings" to "anon";

grant truncate on table "public"."client_apartment_listings" to "anon";

grant update on table "public"."client_apartment_listings" to "anon";

grant delete on table "public"."client_apartment_listings" to "authenticated";

grant insert on table "public"."client_apartment_listings" to "authenticated";

grant references on table "public"."client_apartment_listings" to "authenticated";

grant select on table "public"."client_apartment_listings" to "authenticated";

grant trigger on table "public"."client_apartment_listings" to "authenticated";

grant truncate on table "public"."client_apartment_listings" to "authenticated";

grant update on table "public"."client_apartment_listings" to "authenticated";

grant delete on table "public"."client_apartment_listings" to "service_role";

grant insert on table "public"."client_apartment_listings" to "service_role";

grant references on table "public"."client_apartment_listings" to "service_role";

grant select on table "public"."client_apartment_listings" to "service_role";

grant trigger on table "public"."client_apartment_listings" to "service_role";

grant truncate on table "public"."client_apartment_listings" to "service_role";

grant update on table "public"."client_apartment_listings" to "service_role";

create policy "Enable read access for all users"
on "public"."client_apartment_listings"
as permissive
for select
to public
using (true);



