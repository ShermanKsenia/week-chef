-- If recipies_db was created earlier without migration 001, it may lack `id`.
-- 001 uses CREATE TABLE IF NOT EXISTS, so it never backfilled the column.
DO $$
DECLARE
  has_pk boolean;
BEGIN
  IF to_regclass('public.recipies_db') IS NULL THEN
    RAISE NOTICE '003: public.recipies_db does not exist; run 001 first.';
    RETURN;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'recipies_db' AND column_name = 'id'
  ) THEN
    ALTER TABLE public.recipies_db ADD COLUMN id BIGSERIAL;
    RAISE NOTICE '003: added column recipies_db.id';
  END IF;

  SELECT EXISTS (
    SELECT 1
    FROM pg_constraint c
    JOIN pg_class t ON c.conrelid = t.oid
    JOIN pg_namespace n ON t.relnamespace = n.oid
    WHERE n.nspname = 'public'
      AND t.relname = 'recipies_db'
      AND c.contype = 'p'
  ) INTO has_pk;

  IF NOT has_pk THEN
    ALTER TABLE public.recipies_db ADD CONSTRAINT recipies_db_pkey PRIMARY KEY (id);
    RAISE NOTICE '003: added PRIMARY KEY (id) on recipies_db';
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_recipies_db_label ON public.recipies_db (label);
CREATE INDEX IF NOT EXISTS idx_recipies_db_time_cook ON public.recipies_db (time_cook);
