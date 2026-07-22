from enum import StrEnum

GRADING_CONTAINER_TCP_PORT = 5000
GRADING_CONTAINER_SK = '/run/inginious'

class GradingStatus(StrEnum):
    Crash = 'crash'
    Success = 'success'
