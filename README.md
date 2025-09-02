
# RBN Viagens — Deploy GRÁTIS + Persistente (Koyeb Free + Supabase)

## O que você vai usar (plano grátis)
- **Koyeb**: hospedar o site
- **Supabase**: banco Postgres + Storage (arquivos)

## Passo a passo

1) **Supabase**
   - **SQL Editor** → cole todo o `schema.sql` → **Run**.
   - **Storage → New bucket** → nome `comprovantes` → **Public** → **Create**.
   - **Settings → API** → copie:
     - `Project URL` → `SUPABASE_URL`
     - `service_role key` → `SUPABASE_SERVICE_ROLE_KEY`
   - **Database → Connection string** → copie `DATABASE_URL` (postgres://...)

2) **GitHub**
   - Crie um repo e envie **todos** os arquivos desta pasta.

3) **Koyeb (Free)**
   - Crie o Service a partir do repo.
   - **Environment**:
     - `DATABASE_URL=postgres://...`
     - `SUPABASE_URL=https://SEU-PROJ.supabase.co`
     - `SUPABASE_SERVICE_ROLE_KEY=eyJ...`
     - `SUPABASE_BUCKET=comprovantes`
     - `FLASK_ENV=production`
     - `SECRET_KEY=uma-chave-secreta-forte`
   - **Run command**: `gunicorn -w 2 -k gthread -b 0.0.0.0:$PORT wsgi:app`
   - Deploy.

4) **Usar**
   - Acesse a URL.
   - Login admin: `admin@rbn.local / admin123` (troque depois).
   - Admin cria viagens.
   - Funcionário: **Nova despesa** → escolhe **qualquer viagem** → anexa comprovante (vai para o bucket `comprovantes`).

Pronto. Dados persistem no Supabase.
