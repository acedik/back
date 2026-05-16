# Supabase Setup For AMOUS

1. Create a Supabase project.
2. Open `backend/supabase_schema.sql` in your code editor, copy all of its SQL, paste it into **Supabase Dashboard > SQL Editor**, then click **Run**. Do not type only `supabase_schema.sql`; Supabase needs the SQL inside the file.
3. Open **Storage** and create a public bucket named `client-logos`.
4. Copy your project URL and service role key from **Project Settings > API**.
5. Start the server with these environment variables:

```powershell
$env:AMOUS_ADMIN_PASSWORD="choose-a-strong-admin-password"
$env:AMOUS_SECRET_KEY="choose-a-long-random-secret"
$env:SUPABASE_URL="https://your-project-ref.supabase.co"
$env:SUPABASE_SERVICE_ROLE_KEY="your-service-role-key"
$env:SUPABASE_CLIENT_BUCKET="client-logos"
python backend/app.py
```

Use `http://127.0.0.1:5000/admin` to add, delete, and update company pictures.

Keep `SUPABASE_SERVICE_ROLE_KEY` private. It belongs only on your Python server, never in `index.html`.
