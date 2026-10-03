# LinkedOut: a LinkedIn-style mock

A small full-stack demo app: **React + Vite** frontend, **FastAPI** backend and **MongoDB**, all run with Docker Compose.

Features:
- Sign up and sign in. Passwords are hashed with scrypt; sessions use an HttpOnly cookie.
- Feed of posts with likes and comments; edit or delete your own posts
- Member profiles with an editable About note, plus a resume PDF upload
- Settings: name, username, headline, location, phone, age, gender, date of birth
  (phone, age, gender and date of birth are only ever returned to the member themself)
- Network: suggestions and connections

## Demo accounts

Every demo member signs in with their lowercase first name and the password `test`:
`ada`, `grace`, `linus`, `margaret` (plus `alan` on a fresh database).

To give the members already in a database a login (first name / `test`) and fill in the demo
profiles, run `docker compose exec backend python -m app.seed`. Members listed in
`SKIP_PROFILE_FOR` in `backend/app/seed.py` keep their profile and only get the login.

## Run with Docker

```bash
cd linkedin-mock
cp .env.example .env        # then change the passwords
docker compose up --build
```

| Service  | URL                                   |
|----------|---------------------------------------|
| Frontend | http://localhost:8080                 |
| API      | http://localhost:8000/api/health      |
| API docs | http://localhost:8000/docs            |

MongoDB isn't published to the host. On first start, `mongo/init/01-create-app-user.js` creates a
least-privilege `readWrite` user for the backend, and the backend seeds demo users and posts.
Set `SEED_DATA=false` to turn seeding off.

Reset all data: `docker compose down -v`.

## Local development (without building images)

```bash
# MongoDB only, published on 127.0.0.1:27017
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d mongo

# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
MONGO_URI="mongodb://linkedin_app:<password>@localhost:27017/linkedin_mock?authSource=linkedin_mock" \
  uvicorn app.main:app --reload --port 8000

# Frontend (proxies /api to :8000)
cd frontend
npm install
npm run dev                 # http://localhost:5173
```

## API

Everything except signup, login and health needs the `session` cookie set by login or signup.
The acting member always comes from the session, never from the request body.

| Method | Path                                   | Body / notes                                  |
|--------|----------------------------------------|-----------------------------------------------|
| POST   | `/api/auth/signup`                     | `{name, username, password, headline?, location?}` |
| POST   | `/api/auth/login`                      | `{username, password}`                        |
| POST   | `/api/auth/logout`                     |                                               |
| GET    | `/api/auth/me`                         | the logged-in member                          |
| GET    | `/api/users`                           |                                               |
| GET    | `/api/users/{id}`                      |                                               |
| PATCH  | `/api/users/me`                        | any profile fields; `null` clears optional ones |
| POST   | `/api/users/me/connections`            | `{target_id}`                                 |
| DELETE | `/api/users/me/connections/{id}`       |                                               |
| PUT    | `/api/users/me/resume`                 | multipart `file` (PDF, max 5 MB)              |
| DELETE | `/api/users/me/resume`                 |                                               |
| GET    | `/api/users/{id}/resume?download=`     | the PDF                                       |
| GET    | `/api/posts?author_id=`                |                                               |
| POST   | `/api/posts`                           | `{content}`                                   |
| PATCH  | `/api/posts/{id}`                      | `{content}` (author only)                     |
| DELETE | `/api/posts/{id}`                      | author only                                   |
| POST   | `/api/posts/{id}/like`                 | toggles                                       |
| POST   | `/api/posts/{id}/comments`             | `{text}`                                      |

## Layout

```
linkedin-mock/
  docker-compose.yml
  mongo/init/          first-run init script (app user)
  backend/app/         main.py (routes), auth.py (passwords, sessions), db.py, models.py,
                       seed.py (demo data + update command), config.py
  frontend/src/        App.tsx, api.ts, pages/, components/, styles.css
  frontend/nginx.conf  serves the build and proxies /api to the backend
```
