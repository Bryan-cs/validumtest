# BBC File — Guía de despliegue en Railway

## Arquitectura
- **Backend:** FastAPI + PostgreSQL (Railway)
- **Frontend:** React (Netlify o Railway static)
- **DB:** PostgreSQL automático en Railway

---

## PASO 1 — Crear cuenta en Railway
1. Ve a https://railway.app
2. Sign up con GitHub
3. Plan Hobby ($5/mes) soporta más de 10 usuarios simultáneos

---

## PASO 2 — Desplegar el Backend

### 2a. Subir código a GitHub
```bash
cd bbcfile/backend
git init
git add .
git commit -m "BBC File backend v1"
git remote add origin https://github.com/TU_USUARIO/bbcfile-backend.git
git push -u origin main
```

### 2b. Crear servicio en Railway
1. En Railway → New Project → Deploy from GitHub repo
2. Selecciona `bbcfile-backend`
3. Railway detecta el `Procfile` automáticamente

### 2c. Agregar PostgreSQL
1. En tu proyecto Railway → Add Service → Database → PostgreSQL
2. Railway crea `DATABASE_URL` automáticamente

### 2d. Variables de entorno en Railway
En Settings → Variables, agregar:
```
SECRET_KEY=cambia_esto_por_algo_seguro_aleatorio_largo
ENVIRONMENT=production
ALLOWED_ORIGINS=https://tu-app.netlify.app
```
`DATABASE_URL` y `PORT` los pone Railway automáticamente.

### 2e. Verificar
- Railway te da una URL tipo: `https://bbcfile-backend.up.railway.app`
- Ve a `https://tu-url/docs` para ver la documentación de la API

---

## PASO 3 — Desplegar el Frontend

### Opción A: Netlify (recomendado, gratis)
1. Ve a https://netlify.com
2. Add new site → Import from Git → selecciona tu repo del frontend
3. Build command: `npm run build`
4. Publish directory: `build`
5. Environment variables:
   ```
   REACT_APP_API_URL=https://tu-backend.up.railway.app
   ```

### Opción B: Railway Static
1. Agrega otro servicio en tu proyecto Railway
2. Selecciona el repo del frontend
3. Build command: `npm run build`
4. Start command: `npx serve -s build -l $PORT`

---

## PASO 4 — Primera vez

Al arrancar por primera vez el backend:
- Crea todas las tablas automáticamente
- Crea los usuarios iniciales:
  - **admin** / **admin1234** (rol: admin)
  - **empleado1** / **emp1234** (rol: empleado)
- Crea las listas de referencia (EPS, ARL, etc.)

**IMPORTANTE:** Cambia las contraseñas desde Administración → Usuarios después del primer login.

---

## Estructura de archivos

```
bbcfile/
├── backend/
│   ├── main.py          ← FastAPI app principal
│   ├── database.py      ← Conexión SQLAlchemy
│   ├── models.py        ← Tablas de la DB
│   ├── schemas.py       ← Validación de datos
│   ├── crud.py          ← Toda la lógica de negocio
│   ├── requirements.txt ← Dependencias Python
│   └── Procfile         ← Comando de inicio Railway
│
└── frontend/
    ├── src/
    │   ├── App.jsx              ← Router principal
    │   ├── pages/               ← Páginas del sistema
    │   │   ├── Login.jsx
    │   │   ├── Dashboard.jsx
    │   │   ├── Afiliados.jsx
    │   │   └── Pages.jsx        ← Cobro, Retiros, Facturación, etc.
    │   ├── components/
    │   │   ├── Layout.jsx       ← Sidebar + navegación
    │   │   └── UI.jsx           ← Botones, tablas, modals
    │   ├── hooks/
    │   │   └── useAuth.js       ← Estado de autenticación
    │   └── utils/
    │       └── api.js           ← Cliente HTTP con token automático
    ├── public/index.html
    └── package.json
```

---

## Costos estimados

| Servicio | Plan | Costo |
|---|---|---|
| Railway (backend + DB) | Hobby | ~$5/mes |
| Netlify (frontend) | Starter | Gratis |
| **Total** | | **~$5/mes** |

---

## Desarrollo local

### Backend
```bash
cd bbcfile/backend
pip install -r requirements.txt
uvicorn main:app --reload
# Disponible en http://localhost:8000
# Docs en http://localhost:8000/docs
```

### Frontend
```bash
cd bbcfile/frontend
npm install
npm start
# Disponible en http://localhost:3000
# El proxy en package.json apunta al backend en :8000
```

---

## Notas de seguridad para producción

1. **Cambiar SECRET_KEY** — usa una cadena aleatoria de 32+ caracteres
2. **Cambiar contraseñas** — admin1234 es solo para primer login (el sistema muestra advertencia en logs si no se cambia)
3. **CORS** — configurar `ALLOWED_ORIGINS=https://tu-app.netlify.app` como variable de entorno en Railway
4. **ENVIRONMENT** — configurar `ENVIRONMENT=production` en Railway para bloquear el arranque sin SECRET_KEY
5. **HTTPS** — Railway y Netlify lo proveen automáticamente
6. **Tests locales** — usar `pip install -r requirements-dev.txt` en vez de `requirements.txt`
