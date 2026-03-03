# Verbiage — Supabase (Phase 1)

Phase 1 creates the database schema on Supabase: pgvector + `documents`, `chunks`, `embeddings`.

## You need to do (I can’t connect to Supabase)

1. **Create a Supabase project** at [supabase.com](https://supabase.com) → New project.  
   Save: **Project URL**, **Database password**, and (optional) **anon** / **service_role** keys from Project Settings → API.

2. **Run the schema SQL** in the Supabase **SQL Editor**:
   - Open your project → **SQL Editor** → New query.
   - Paste the contents of `migrations/20250302000000_phase1_schema.sql`.
   - Run it.

3. **Get your Postgres connection string** for Phase 2:  
   Project Settings → **Database** → Connection string (URI). Use the **pooler** URI (port 6543) for short-lived connections from the FastAPI app.

After that, Phase 1 is done: pgvector enabled, tables and indexes (including HNSW for vector search) are created.

## Optional: Supabase CLI

If you use the [Supabase CLI](https://supabase.com/docs/guides/cli) and link this project (`supabase link`), you can apply the migration with:

```bash
supabase db push
```

(or run the migration file manually from the CLI).
