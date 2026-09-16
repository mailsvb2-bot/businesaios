from enum import Enum


class PaymentStatus(str, Enum):
    PENDING = "pending"
    SETTLED = "settled"
    FAILED = "failed"
    REFUNDED = "refunded"
class PayoutStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    CANCELED = "canceled"
class ExpenseCategory(str, Enum):
    PAYROLL = "payroll"
    MARKETING = "marketing"
    TOOLS = "tools"
    TAX = "tax"
    OPERATIONS = "operations"
    OTHER = "other"
class ExpenseLifecycleStatus(str, Enum):
    RECORDED = "recorded"
    VOIDED = "voided"

class FinanceSnapshotStatus(str, Enum):
    OK = "ok"
    WARNING = "warning"
    BLOCKED = "blocked"
