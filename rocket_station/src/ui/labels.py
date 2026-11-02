from src.domain.enums import OperationKind, Review

KIND_LABELS = {OperationKind.STATIC_TEST: 'Teste estático', OperationKind.FLIGHT: 'Voo'}
REVIEW_LABELS = {
    Review.PENDING: 'Pendente',
    Review.APPROVED: 'Deferido',
    Review.REJECTED: 'Indeferido',
    Review.NOT_APPLICABLE: 'Não se aplica',
}