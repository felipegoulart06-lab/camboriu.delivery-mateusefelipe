"""Validações de documentos brasileiros usadas nos cadastros."""
import re

from django.core.exceptions import ValidationError

CNPJ_WEIGHTS_FIRST = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
CNPJ_WEIGHTS_SECOND = [6] + CNPJ_WEIGHTS_FIRST
PLATE_OLD = re.compile(r"^[A-Z]{3}[0-9]{4}$")
PLATE_MERCOSUL = re.compile(r"^[A-Z]{3}[0-9][A-Z][0-9]{2}$")
CHASSIS = re.compile(r"^[A-HJ-NPR-Z0-9]{17}$")


def digits(value):
    return "".join(char for char in str(value or "") if char.isdigit())


def _check_digit(numbers, weights):
    total = sum(number * weight for number, weight in zip(numbers, weights))
    rest = total % 11
    return 0 if rest < 2 else 11 - rest


def clean_cpf(value):
    """Devolve o CPF formatado ou levanta erro se os dígitos verificadores não fecharem."""
    numbers = digits(value)
    if len(numbers) != 11:
        raise ValidationError("CPF deve ter 11 dígitos.")
    if numbers == numbers[0] * 11:
        raise ValidationError("CPF inválido.")
    body = [int(char) for char in numbers]
    first = _check_digit(body[:9], range(10, 1, -1))
    second = _check_digit(body[:10], range(11, 1, -1))
    if [first, second] != body[9:]:
        raise ValidationError("CPF inválido. Confira os números digitados.")
    return f"{numbers[:3]}.{numbers[3:6]}.{numbers[6:9]}-{numbers[9:]}"


def clean_cnpj(value):
    """Devolve o CNPJ formatado ou levanta erro se os dígitos verificadores não fecharem."""
    numbers = digits(value)
    if len(numbers) != 14:
        raise ValidationError("CNPJ deve ter 14 dígitos.")
    if numbers == numbers[0] * 14:
        raise ValidationError("CNPJ inválido.")
    body = [int(char) for char in numbers]
    first = _check_digit(body[:12], CNPJ_WEIGHTS_FIRST)
    second = _check_digit(body[:13], CNPJ_WEIGHTS_SECOND)
    if [first, second] != body[12:]:
        raise ValidationError("CNPJ inválido. Confira os números digitados.")
    return f"{numbers[:2]}.{numbers[2:5]}.{numbers[5:8]}/{numbers[8:12]}-{numbers[12:]}"


def clean_plate(value):
    plate = re.sub(r"[^A-Za-z0-9]", "", str(value or "")).upper()
    if not (PLATE_OLD.match(plate) or PLATE_MERCOSUL.match(plate)):
        raise ValidationError("Placa inválida. Use o padrão ABC1234 ou Mercosul ABC1D23.")
    return plate


def clean_renavam(value):
    """RENAVAM tem 11 dígitos, com o último calculado sobre os dez primeiros."""
    numbers = digits(value).zfill(11)
    if len(numbers) != 11:
        raise ValidationError("RENAVAM deve ter 11 dígitos.")
    weights = [3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    total = sum(int(char) * weight for char, weight in zip(numbers[:10], weights))
    rest = (total * 10) % 11
    expected = 0 if rest == 10 else rest
    if expected != int(numbers[10]):
        raise ValidationError("RENAVAM inválido. Confira o número no CRLV.")
    return numbers


def clean_chassis(value):
    """O chassi tem 17 posições e não usa as letras I, O e Q."""
    chassis = re.sub(r"[^A-Za-z0-9]", "", str(value or "")).upper()
    if not CHASSIS.match(chassis):
        raise ValidationError("Chassi inválido. São 17 caracteres, sem as letras I, O e Q.")
    return chassis


def clean_zip_code(value):
    numbers = digits(value)
    if len(numbers) != 8:
        raise ValidationError("CEP deve ter 8 dígitos.")
    return f"{numbers[:5]}-{numbers[5:]}"


def clean_phone(value):
    numbers = digits(value)
    if len(numbers) not in (10, 11):
        raise ValidationError("Telefone deve ter DDD mais 8 ou 9 dígitos.")
    prefix, rest = numbers[:2], numbers[2:]
    return f"({prefix}) {rest[:-4]}-{rest[-4:]}"
