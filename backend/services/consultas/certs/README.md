# Intermedios que la fuente no envia

`aplicaciones.adres.gov.co` sirve una cadena TLS incompleta: el certificado del
sitio (`CN=*.adres.gov.co`) lo emite **Go Daddy Secure Certificate Authority -
G2**, pero el servidor adjunta un intermedio de **Sectigo** que no corresponde.

Los navegadores y curl lo resuelven solos porque descargan el intermedio via
AIA. Python no hace AIA fetching, asi que `httpx` falla con
`CERTIFICATE_VERIFY_FAILED: unable to get local issuer certificate`.

La salida NO es `verify=False`. Por ese canal viajan datos de salud de personas
identificadas; desactivar la verificacion lo deja abierto a un intermediario.
Lo que se hace es suministrar el intermedio que el servidor olvido, y seguir
verificando contra certifi + este archivo. La cadena queda completa:

    *.adres.gov.co
      -> Go Daddy Secure Certificate Authority - G2   (este archivo)
        -> Go Daddy Root Certificate Authority - G2   (ya esta en certifi)

## godaddy_g2_intermediate.pem

Origen: https://certs.godaddy.com/repository/gdig2.crt.pem
Subject: CN=Go Daddy Secure Certificate Authority - G2
Issuer:  CN=Go Daddy Root Certificate Authority - G2
Vence:   2031-05-03

**Vence en 2031.** Si antes de esa fecha ADRES cambia de CA, el test de
contrato (`pytest -m red tests/test_contrato_adres.py`) falla con error de TLS:
ahi se reemplaza este archivo por el intermedio nuevo.
