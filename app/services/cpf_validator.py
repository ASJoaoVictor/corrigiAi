import re

def normalize_cpf(value):
    return re.sub(r'[^0-9]', '', str(value or ''))

def validate_cpf(value):
    cpf = normalize_cpf(value)
    if len(cpf) != 11 or len(set(cpf)) == 1:
        return False
    for size in (9,10):
        digit = (sum(int(cpf[i])*(size+1-i) for i in range(size))*10)%11
        if (0 if digit == 10 else digit) != int(cpf[size]):
            return False
    return True

def mask_cpf(value):
    cpf = normalize_cpf(value)
    return '***.***.***-' + (cpf[-2:] if len(cpf)==11 else '??')
