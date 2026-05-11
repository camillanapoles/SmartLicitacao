"""CNPJ format validation — alfanumérico-ready para IN 2.229/2024.

A Receita Federal IN 2.229/2024 introduz CNPJs alfanuméricos (12 chars [A-Z0-9]
+ 2 dígitos verificadores) com vigência a partir de 01/07/2026. Este módulo
centraliza a validação de formato para backend e sitemap, eliminando o uso de
str.isdigit e `length >= 11` que (a) rejeitariam CNPJs futuros e (b) aceitam
CPFs (11 dígitos) e strings inválidas, causando páginas 404 no GSC.

Uso:
    from utils.cnpj_validator import is_valid_cnpj_format, normalize_cnpj

    if is_valid_cnpj_format("12.345.678/0001-95"):
        ...  # True — CNPJ numérico com máscara
    if is_valid_cnpj_format("AB3DEF78000195"):
        ...  # True — CNPJ alfanumérico futuro (01/07/2026)
"""

import re

# CNPJ sem máscara: 12 chars alfanuméricos (A-Z0-9) + 2 dígitos verificadores
_CNPJ_PATTERN = re.compile(r'^[A-Z0-9]{12}\d{2}$', re.IGNORECASE)

# CPF sem máscara: exatamente 11 dígitos — deve ser rejeitado
_CPF_PATTERN = re.compile(r'^\d{11}$')

# Caracteres de máscara CNPJ: pontos, barras, hífens
_STRIP_MASK = re.compile(r'[.\-/]')

# Remove qualquer char não alfanumérico (genérico, para normalize_cnpj)
_STRIP_NON_ALNUM = re.compile(r'[^A-Z0-9]')


def is_valid_cnpj_format(c: str) -> bool:
    """Valida formato CNPJ — alfanumérico-ready para 01/07/2026 (IN 2.229/2024).

    Aceita:
    - CNPJ numérico sem máscara: "12345678000195" (14 dígitos)
    - CNPJ alfanumérico futuro: "AB3DEF78000195" (12 alnum + 2 dígitos)
    - CNPJ com máscara padrão: "12.345.678/0001-95"

    Rejeita:
    - CPF (11 dígitos puramente numéricos)
    - Strings com menos ou mais de 14 caracteres úteis
    - None, vazio, tipos não-string
    """
    if not c or not isinstance(c, str):
        return False
    normalized = _STRIP_MASK.sub('', c.upper())
    # Deve ter exatamente 14 chars após remoção de máscara, ser alfanumérico
    # no padrão CNPJ, e não ser um CPF (11 dígitos)
    return bool(_CNPJ_PATTERN.match(normalized)) and not bool(_CPF_PATTERN.match(normalized))


def normalize_cnpj(c: str) -> str:
    """Remove formatação, retorna string limpa uppercase.

    "12.345.678/0001-95" → "12345678000195"
    "ab3def78000195" → "AB3DEF78000195"
    "" → ""
    None → ""
    """
    return _STRIP_NON_ALNUM.sub('', (c or '').upper())
