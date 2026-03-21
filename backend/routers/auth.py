"""Router de autenticación."""
from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy.orm import Session
from datetime import timedelta
import jwt
from database import get_db
import schemas, crud
from .deps import (
    SECRET_KEY, ALGORITHM, REFRESH_TOKEN_EXPIRE_DAYS,
    create_token, verify_token, security,
)
from fastapi.security import HTTPAuthorizationCredentials
from slowapi import Limiter
from slowapi.util import get_remote_address

_limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
@_limiter.limit("20/minute")
def login(request: Request, data: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = crud.get_user_by_username(db, data.username)
    if not user or not user.activo:
        raise HTTPException(status_code=401, detail="Usuario no encontrado o inactivo")
    if not user.password or not crud.verify_password(data.password, user.password):
        raise HTTPException(status_code=401, detail="Contraseña incorrecta")
    # Migrar passwords en texto plano a bcrypt
    if user.password and not user.password.startswith("$2"):
        user.password = crud.hash_password(data.password)
        db.commit()

    token_data = {"sub": user.username, "rol": user.rol, "nombre": user.nombre}
    access_token = create_token(token_data)
    refresh_token = create_token(
        {**token_data, "type": "refresh"},
        expires=timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    )
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "rol": user.rol,
        "nombre": user.nombre,
        "username": user.username,
    }


@router.post("/refresh")
def refresh_token(body: dict):
    """Obtiene un nuevo access token usando el refresh token."""
    rt = body.get("refresh_token", "")
    if not rt:
        raise HTTPException(status_code=401, detail="refresh_token requerido")
    try:
        payload = jwt.decode(rt, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Token no es de tipo refresh")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Refresh token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Refresh token inválido")

    new_access = create_token({"sub": payload["sub"], "rol": payload["rol"], "nombre": payload.get("nombre", "")})
    return {"access_token": new_access, "token_type": "bearer"}


@router.get("/me")
def me(token=Depends(verify_token)):
    return token
