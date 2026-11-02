from enum import Enum


class OperationKind(str, Enum):
    STATIC_TEST = 'static_test'
    FLIGHT = 'flight'


class Review(str, Enum):
    PENDING = 'pending'
    APPROVED = 'approved'
    REJECTED = 'rejected'
    NOT_APPLICABLE = 'not_applicable'

class SourceKind(str, Enum):
    SD = 'sd'
    RADIO = 'radio'

class Axis(str, Enum):
    LEFT = 'left'
    RIGHT = 'right'