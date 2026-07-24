"""Aislamiento multi-tenant a nivel de sesión SQLAlchemy.

Mecanismo central (defensa en profundidad): un ContextVar guarda la organización activa de la
petición actual y un listener `do_orm_execute` inyecta automáticamente
`WHERE organizacion_id = <org>` en TODA consulta ORM de lectura sobre modelos con `organizacion_id`.

Así, aunque un endpoint olvide filtrar, las lecturas quedan acotadas a la organización activa y no
se filtran datos entre organizaciones. Las escrituras (INSERT) siguen seteando `organizacion_id`
explícitamente; el listener no cubre bulk UPDATE/DELETE, que se filtran a mano en el CRUD.

Modelos excluidos del auto-filtro:
- `Usuario`  → el superadmin (sin organización) debe poder listar/gestionar usuarios de cualquier org.
- `Organizacion`, `LoginAttempt`, `TokenBlacklist` → globales, no tienen `organizacion_id`.
"""
from contextvars import ContextVar
from typing import Optional
from sqlalchemy import event
from sqlalchemy.orm import Session, with_loader_criteria


class TenantContextError(Exception):
    """Se intentó escribir un modelo tenant sin organización activa ni organizacion_id explícito."""

# Organización activa de la petición. None = sin scoping (superadmin en rutas de gestión,
# tareas de sistema/scheduler, o peticiones sin autenticar que igualmente rechazan los deps).
current_org_id: ContextVar[Optional[int]] = ContextVar("current_org_id", default=None)

# Se rellena en la primera consulta (lazy import para evitar ciclo con models).
_TENANT_MODELS = None


def _tenant_models():
    global _TENANT_MODELS
    if _TENANT_MODELS is None:
        import models
        excluidos = {"Usuario", "Organizacion", "LoginAttempt", "TokenBlacklist"}
        _TENANT_MODELS = [
            m for m in (
                models.Afiliado, models.Factura, models.Retiro, models.Eliminado,
                models.Empleado, models.Gasto, models.IngresoAdicional, models.NominaMensual,
                models.Config, models.Lista, models.SolicitudNovedad, models.NovedadPago,
                models.SolicitudRetiro, models.Actividad, models.Tarea, models.TareaComentario,
                models.Notificacion, models.PlanillaPago, models.Documento, models.AvisoCliente,
                models.CredencialPortal, models.SeguimientoArl,
            ) if m.__name__ not in excluidos
        ]
    return _TENANT_MODELS


def set_org(org_id: Optional[int]):
    """Fija la organización activa para la petición. Devuelve el token para restaurar."""
    return current_org_id.set(org_id)


def reset_org(token):
    current_org_id.reset(token)


def _tenant_model_names():
    return {m.__name__ for m in _tenant_models()}


@event.listens_for(Session, "before_flush")
def _stamp_tenant_on_insert(session, flush_context, instances):
    """Auto-rellena organizacion_id en objetos nuevos de modelos tenant desde la organización activa.
    Si un objeto ya trae organizacion_id explícito, se respeta (p.ej. provisión por el superadmin)."""
    org = current_org_id.get()
    names = _tenant_model_names()
    for obj in session.new:
        if type(obj).__name__ in names and getattr(obj, "organizacion_id", None) is None:
            if org is None:
                # Sin organización activa y sin valor explícito → error ruidoso (nunca fila huérfana).
                raise TenantContextError(
                    f"{type(obj).__name__} creado sin organizacion_id y sin organización activa")
            obj.organizacion_id = org


@event.listens_for(Session, "do_orm_execute")
def _apply_tenant_filter(execute_state):
    # Aplica a SELECT y también a UPDATE/DELETE ORM masivos (Query.update()/delete()), para que un
    # id de otra organización no pueda ser modificado/borrado. Ignora cargas de columnas/relaciones
    # y el opt-out explícito execution_options(skip_tenant=True).
    if not (execute_state.is_select or execute_state.is_update or execute_state.is_delete):
        return
    if execute_state.is_column_load or execute_state.is_relationship_load:
        return
    if execute_state.execution_options.get("skip_tenant"):
        return
    org = current_org_id.get()
    if org is None:
        return
    stmt = execute_state.statement
    for model in _tenant_models():
        stmt = stmt.options(
            with_loader_criteria(model, model.organizacion_id == org, include_aliases=True)
        )
    execute_state.statement = stmt
