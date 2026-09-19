"""Consultas a fuentes oficiales de seguridad social.

Cada fuente expone dos pasos porque todas exigen código de seguridad (captcha):

    iniciar(tipo_doc, doc) -> EstadoConsulta + imagen del captcha
    resolver(estado, captcha_texto) -> ResultadoConsulta

El captcha lo resuelve SIEMPRE una persona (el empleado que está haciendo el
alta). No se usan servicios de resolución automática: son frágiles, cuestan por
resolución y son justamente lo que la fuente bloquea.

Consecuencia de diseño: no hay revalidación masiva en lote. Una consulta = un
captcha = un humano. El módulo sirve para el alta, no para barridos.
"""
from .adres import ConsultaADRES, FuenteNoDisponible, CaptchaIncorrecto, SinResultados

__all__ = ["ConsultaADRES", "FuenteNoDisponible", "CaptchaIncorrecto", "SinResultados"]
