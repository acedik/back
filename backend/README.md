# AMOUS Backend

Python Flask backend for the AMOUS website admin/API.

## Run Locally

```powershell
pip install -r requirements.txt
python app.py
```

Admin URL:

```text
http://127.0.0.1:5000/admin
```

## Environment

Create `backend/.env` locally:

```env
AMOUS_ADMIN_PASSWORD=your-admin-password
AMOUS_SECRET_KEY=long-random-secret
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
SUPABASE_CLIENT_BUCKET=client-logos
```

Keep `.env`, `data/`, and `uploads/` private.

## Supabase

Run `supabase_schema.sql` in Supabase SQL Editor and create a public Storage bucket named `client-logos`.
