class ValidationError(ValueError):
    """Dado inválido. A mensagem é mostrada ao usuário."""

class OperationExistsError(Exception):
    """Já existe uma operação com este código."""

class OperationNotFoundError(Exception):
    """A operação não existe."""

class InvalidPackageError(ValueError):
    """O arquivo de pacote não pode ser importado. A mensagem é mostrada ao usuário."""

class InvalidCsvError(ValueError):
    """O arquivo CSV não pode ser lido. A mensagem é mostrada ao usuário."""

class CalculationError(Exception):
    """O cálculo não pôde ser feito. A mensagem é mostrada ao usuário."""