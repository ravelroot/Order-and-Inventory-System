import re

_NAO_DIGITO = re.compile(r"\D")


def so_digitos(valor: str | None) -> str:
    return _NAO_DIGITO.sub("", valor or "")


def _digito_cpf(base: str) -> str:
    peso = len(base) + 1
    soma = sum(int(d) * (peso - i) for i, d in enumerate(base))
    resto = (soma * 10) % 11
    return "0" if resto == 10 else str(resto)


def cpf_valido(valor: str) -> bool:
    cpf = so_digitos(valor)
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    return cpf[9] == _digito_cpf(cpf[:9]) and cpf[10] == _digito_cpf(cpf[:10])


def completar_cpf(base9: str) -> str:
    d1 = _digito_cpf(base9)
    return base9 + d1 + _digito_cpf(base9 + d1)


_PESOS_CNPJ_1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
_PESOS_CNPJ_2 = [6, *_PESOS_CNPJ_1]


def _digito_cnpj(base: str, pesos: list[int]) -> str:
    soma = sum(int(d) * p for d, p in zip(base, pesos, strict=True))
    resto = soma % 11
    return "0" if resto < 2 else str(11 - resto)


def cnpj_valido(valor: str) -> bool:
    cnpj = so_digitos(valor)
    if len(cnpj) != 14 or cnpj == cnpj[0] * 14:
        return False
    return cnpj[12] == _digito_cnpj(cnpj[:12], _PESOS_CNPJ_1) and cnpj[13] == _digito_cnpj(cnpj[:13], _PESOS_CNPJ_2)


def completar_cnpj(base12: str) -> str:
    d1 = _digito_cnpj(base12, _PESOS_CNPJ_1)
    return base12 + d1 + _digito_cnpj(base12 + d1, _PESOS_CNPJ_2)


def formatar_documento(valor: str) -> str:
    d = so_digitos(valor)
    if len(d) == 11:
        return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"
    if len(d) == 14:
        return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"
    return valor


def mascarar_documento(valor: str) -> str:
    d = so_digitos(valor)
    if len(d) == 11:
        return f"***.{d[3:6]}.***-{d[9:]}"
    if len(d) == 14:
        return formatar_documento(d)
    return "***"


def ean13_digito(base12: str) -> str:
    soma = sum(int(d) * (3 if i % 2 else 1) for i, d in enumerate(base12))
    return str((10 - soma % 10) % 10)


def ean13_valido(valor: str) -> bool:
    d = so_digitos(valor)
    return len(d) == 13 and d[-1] == ean13_digito(d[:12])


UFS = frozenset("AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split())
