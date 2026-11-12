"""Shared labels for optional, explicitly recorded weighing context."""

WASTE_REASONS = (
    {"code": "unspecified", "label": "Не указана"},
    {"code": "preparation", "label": "Очистки и подготовка"},
    {"code": "overproduction", "label": "Приготовили лишнее"},
    {"code": "spoilage", "label": "Порча/истёк срок"},
    {"code": "plate_leftovers", "label": "Остатки после еды"},
    {"code": "other", "label": "Другая причина"},
)
REASON_LABELS = {item["code"]: item["label"] for item in WASTE_REASONS}
