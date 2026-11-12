"""Grounded local analyst: deterministic tool planning plus real anomaly ML.

No model API, web access, database access or mutation is performed here. The
caller must supply permission-scoped accepted data. Narrative explanations are
templates over tool results, not an unrestricted language model.
"""

from __future__ import annotations

import calendar
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from importlib.util import find_spec
import math
import statistics
from typing import Any

from .analytics import calculate_ecology, row_mass, summarize
from .metrics import calculate_intensity

MODEL_DESCRIPTION = "Локальная модель IsolationForest ищет необычные ежедневные массы отдельно по организации и виду отходов. План инструментов и текст ответа формируются правилами."
DISCLAIMER = "Агент читает только доступные вам принятые отчёты. Это локальный аналитик с ML, без внешней языковой модели. Аномалия — повод проверить запись, а не установленная причина потерь."
LIMITATIONS = [
    "Обучение использует только принятые наблюдения, строго предшествующие окну проверки.",
    "Требуется минимум 10 исторических дней для каждой пары организация/вид отходов.",
    "Оценка модели не является вероятностью ошибки, доказательством нарушения или объяснением причины.",
    "Литры без плотности исключены из анализа массы; демонстрационные данные не подтверждают эффект внедрения.",
]


def _model_info(available: bool | None = None) -> dict:
    if available is None:
        available = find_spec("sklearn") is not None
    return {"name": "IsolationForest", "available": available, "description": MODEL_DESCRIPTION}


def _accepted(rows):
    return [dict(row) for row in rows if row.get("report_status", row.get("status", "accepted")) == "accepted"]


def _day(value):
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _aggregate_days(rows):
    groups = {}
    for row in rows:
        when = _day(row.get("date"))
        mass = row_mass(row)
        if when is None or mass is None:
            continue
        key = (row.get("organization_id"), row.get("waste_type_id"))
        if key not in groups:
            groups[key] = {
                "organization_id": key[0], "organization_name": row.get("organization_name", "—"),
                "waste_type_id": key[1], "waste_name": row.get("waste_name", "—"),
                "days": defaultdict(lambda: Decimal("0")), "entry_ids": defaultdict(list),
            }
        groups[key]["days"][when] += mass
        if row.get("id") is not None:
            groups[key]["entry_ids"][when].append(row["id"])
    return groups


def detect_anomalies(rows, history) -> dict:
    """Score the last 14 calendar days present in the selected period.

Each group is trained once on up to 180 earlier days. Candidate dates and
future history can never enter training. Missing days are not invented as
zero-waste measurements.
"""
    rows = _accepted(list(rows))
    history = _accepted(list(history))
    selected_dates = sorted({_day(row.get("date")) for row in rows} - {None})
    training = {"groups_total": 0, "groups_trained": 0, "groups_skipped": 0, "observations": 0,
                "training_max_date": None, "scoring_from": None, "scoring_to": None, "min_history_days": 10}
    result = {"items": [], "model": _model_info(), "training": training, "limitations": list(LIMITATIONS)}
    if not selected_dates:
        result["limitations"].insert(0, "В выбранном периоде нет принятых записей для анализа.")
        return result
    scoring_end = selected_dates[-1]
    scoring_start = max(selected_dates[0], scoring_end - timedelta(days=13))
    training["scoring_from"] = scoring_start.isoformat()
    training["scoring_to"] = scoring_end.isoformat()
    candidates = _aggregate_days([row for row in rows if scoring_start <= _day(row["date"]) <= scoring_end])
    historical = _aggregate_days([row for row in history if _day(row.get("date")) is not None and _day(row["date"]) < scoring_start])
    training["groups_total"] = len(candidates)
    if not result["model"]["available"]:
        result["limitations"].insert(0, "Модель недоступна: установите зависимости проекта, включая scikit-learn.")
        training["groups_skipped"] = len(candidates)
        return result
    try:
        from sklearn.ensemble import IsolationForest
    except ImportError:
        result["model"] = _model_info(False)
        result["limitations"].insert(0, "Не удалось загрузить scikit-learn. Остальные расчёты продолжают работать.")
        training["groups_skipped"] = len(candidates)
        return result

    latest_training_day = None
    for key, candidate in candidates.items():
        old = historical.get(key)
        past_days = sorted(old["days"]) [-180:] if old else []
        if len(past_days) < 10:
            training["groups_skipped"] += 1
            continue
        past_values = [float(old["days"][day]) for day in past_days]
        # A constant series has no learned scale: report insufficiency rather
        # than claim that a zero-width distribution validates every value.
        if len({round(value, 6) for value in past_values}) < 3:
            training["groups_skipped"] += 1
            continue
        observations = [[math.log1p(value)] for value in past_values]
        # Do not assume that 5% of historical measurements were bad. The
        # estimator's standard automatic threshold is an uncalibrated flag,
        # explicitly presented as a reason to inspect the source records.
        model = IsolationForest(n_estimators=48, contamination="auto", random_state=42,
                                max_samples=min(128, len(observations)), n_jobs=1)
        model.fit(observations)
        target_days = sorted(candidate["days"])
        target_values = [float(candidate["days"][day]) for day in target_days]
        targets = [[math.log1p(value)] for value in target_values]
        labels = model.predict(targets)
        scores = model.score_samples(targets)
        decisions = model.decision_function(targets)
        average = statistics.mean(past_values)
        training["groups_trained"] += 1
        training["observations"] += len(past_days)
        latest_training_day = max(latest_training_day, past_days[-1]) if latest_training_day else past_days[-1]
        for day, amount, label, score, decision in zip(target_days, target_values, labels, scores, decisions):
            if int(label) != -1:
                continue
            percent = (amount - average) / average * 100 if average > 0 else None
            direction = "выше" if amount > average else "ниже"
            result["items"].append({
                "organization_id": candidate["organization_id"], "organization_name": candidate["organization_name"],
                "waste_type_id": candidate["waste_type_id"], "waste_name": candidate["waste_name"],
                "date": day.isoformat(), "mass_kg": round(amount, 6), "expected_mean_kg": round(average, 6),
                "deviation_percent": round(percent, 2) if percent is not None else None,
                "score": round(-float(score), 6), "decision_score": round(float(decision), 6),
                "entry_ids": candidate["entry_ids"][day], "training_days": len(past_days),
                "training_from": past_days[0].isoformat(), "training_to": past_days[-1].isoformat(),
                "message": f"Масса {direction} среднего исторического уровня. Проверьте единицу, повторные записи и условия работы подразделения.",
            })
    training["training_max_date"] = latest_training_day.isoformat() if latest_training_day else None
    result["items"].sort(key=lambda item: (item["decision_score"], item["date"], str(item["organization_id"])))
    result["items"] = result["items"][:30]
    if not training["groups_trained"]:
        result["limitations"].insert(0, "Недостаточно разнообразной более ранней истории: ML-вывод не сформирован.")
    return result


def _format(value, digits=2):
    if value is None:
        return "не рассчитано"
    return f"{float(value):,.{digits}f}".replace(",", " ").replace(".", ",")


def _previous_period(start, end):
    first, last = _day(start), _day(end)
    if first is None or last is None or first > last:
        return None, None
    months = (last.year - first.year) * 12 + last.month - first.month + 1
    if first.day == 1 and last.day == calendar.monthrange(last.year, last.month)[1]:
        end_previous = first - timedelta(days=1)
        absolute_month = first.year * 12 + first.month - 1 - months
        start_previous = date(absolute_month // 12, absolute_month % 12 + 1, 1)
        return start_previous, end_previous
    duration = last - first + timedelta(days=1)
    return first - duration, first - timedelta(days=1)


def respond(message: str, rows, history, missing, scope: dict) -> dict:
    message = str(message or "").strip()[:2000]
    normalized = message.lower().replace("ё", "е")
    rows = _accepted(list(rows))
    history = _accepted(list(history))
    missing_items = list(missing.get("items", [])) if isinstance(missing, dict) else list(missing or [])
    missing_month = missing.get("month") if isinstance(missing, dict) else None
    output = {
        "answer": "", "tools": [], "evidence": [], "suggestions": [], "anomalies": [],
        "model": _model_info(), "scope": dict(scope), "disclaimer": DISCLAIMER,
    }

    def tool(name, label):
        output["tools"].append({"name": name, "label": label, "status": "completed"})

    def fact(label, value, unit=None):
        output["evidence"].append({"label": label, "value": value, **({"unit": unit} if unit else {})})

    forbidden_action = any(word in normalized for word in ("удали", "удалить", "прими отчет", "прими отчёт", "принять отчет", "отправь отчет", "измени запись", "запиши ", "создай запись"))
    if forbidden_action:
        output["answer"] = "Я анализирую данные и показываю рекомендации. Для добавления и исправления записей откройте «Мои отчёты», для принятия — «Проверка отчётов». Изменение выполнит пользователь с соответствующей ролью; сейчас данные не изменены."
        output["suggestions"] = ["Покажи общую сводку", "Какие отчёты ещё не приняты?", "Найди необычные объёмы отходов"]
        return output
    if not normalized or any(word in normalized for word in ("что уме", "помощ", "привет", "здравств")):
        output["answer"] = "Я локальный аналитик FoodSave. Могу собрать сводку, показать отмеченные причины и кг на 100 порций, сравнить периоды, объяснить CO₂, показать несданные отчёты и проверить необычные массы моделью IsolationForest. Выберите период и организацию в фильтрах: ответы будут только по доступным вам данным."
        output["suggestions"] = ["Покажи общую сводку", "Покажи причины отходов", "Сколько кг на 100 порций?", "Объясни расчёт CO₂", "Кто ещё не сдал отчёт?"]
        return output

    wants_ecology = any(word in normalized for word in ("co2", "co₂", "со2", "со₂", "эколог", "углер", "выброс"))
    wants_missing = any(word in normalized for word in ("сдал", "сдач", "сдан", "отчет", "отчёт", "провер", "вернул", "возврат")) and not any(word in normalized for word in ("аномал", "необыч"))
    wants_anomaly = any(word in normalized for word in ("аномал", "необыч", "подозр", "скачок", "скачки", "отклон"))
    wants_economy = any(word in normalized for word in ("эконом", "окуп", "стоим", "денег", "тенге", "затрат"))
    wants_trend = any(word in normalized for word in ("сравн", "динамик", "тренд", "изменил", "рост", "вырос", "снизил", "предыдущ"))
    wants_reasons = "причин" in normalized
    wants_intensity = any(word in normalized for word in ("порци", "кг/100", "интенсивност", "удельн", "нормир"))
    wants_recommend = any(word in normalized for word in ("совет", "рекоменд", "сократ", "улучш", "почему"))
    wants_summary = not any((wants_ecology, wants_missing, wants_anomaly, wants_economy, wants_trend, wants_reasons, wants_intensity))

    previous_from, previous_to = _previous_period(scope.get("from"), scope.get("to"))
    previous = [row for row in history if previous_from and _day(row.get("date")) and previous_from <= _day(row["date"]) <= previous_to]
    dashboard = summarize(rows, previous)
    totals = dashboard["totals"]
    chunks = []
    tool("accepted_summary", "Сводка принятых записей")
    period = f"{scope.get('from', '—')} — {scope.get('to', '—')}"
    chunks.append(f"Период: {period}. Принято {totals['records']} записей; известная масса — {_format(totals['known_mass_kg'])} кг.")
    fact("Принятых записей", totals["records"])
    fact("Известная масса", totals["known_mass_kg"], "кг")
    if totals["volume_l"]:
        chunks.append(f"Исходный объём учтён отдельно: {_format(totals['volume_l'])} л. В общую массу включены только литры с известной плотностью.")
    if totals["unconverted_l"]:
        chunks.append(f"Для {_format(totals['unconverted_l'])} л плотность неизвестна; масса и экологический результат для них не рассчитаны.")
        fact("Литры без плотности", totals["unconverted_l"], "л")

    if wants_reasons:
        tool("recorded_reasons", "Причины, отмеченные сотрудниками")
        reasons = dashboard["by_reason"]
        if not reasons:
            chunks.append("В выбранной принятой выборке нет записей с причинами.")
        else:
            chunks.append("Категории причин указаны сотрудниками; сводка не устанавливает причинную связь. Старые и незаполненные записи относятся к «Не указана».")
            for reason in reasons:
                chunks.append(
                    f"• {reason['label']}: {reason['records']} записей, исходно {_format(reason['raw_kg'])} кг "
                    f"и {_format(reason['volume_l'])} л; известная масса {_format(reason['known_mass_kg'])} кг."
                )
                fact(f"Причина: {reason['label']} — записей", reason["records"])

    if wants_intensity or wants_summary:
        tool("matched_portion_intensity", "Масса на 100 порций по сопоставленным дням")
        intensity = scope.get("intensity")
        if not isinstance(intensity, dict):
            intensity = calculate_intensity(rows, [])
        if intensity["kg_per_100_portions"] is not None:
            chunks.append(
                f"На 100 порций приходится {_format(intensity['kg_per_100_portions'], 3)} кг выбранных отходов. "
                f"Расчёт: {_format(intensity['covered_mass_kg'])} кг / {intensity['portions']} порций × 100; "
                f"покрыты все {intensity['total_days']} дней организаций с взвешиваниями."
            )
        else:
            chunks.append(intensity["message"])
            if intensity["covered_kg_per_100_portions"] is not None:
                chunks.append(
                    f"Только по покрытым дням: {_format(intensity['covered_kg_per_100_portions'], 3)} кг/100 порций "
                    f"({_format(intensity['covered_mass_kg'])} кг / {intensity['portions']} порций × 100). "
                    "Этот частичный показатель не описывает весь период."
                )
            if intensity["total_days"]:
                chunks.append(
                    f"Дней без числа порций: {intensity['missing_days']}; с 0 порций: {intensity['zero_portion_days']}; "
                    f"с неизвестной массой: {intensity['unknown_mass_days']}. Эти причины неполноты могут совпадать в одном дне."
                )
        chunks.append("Порции каждого дня организации учитываются один раз. Дни обслуживания без взвешиваний не означают нулевые отходы и исключены из показателя. При фильтре вида или способа используется масса только выбранных строк.")
        fact("Кг на 100 порций по всем дням с взвешиваниями", intensity["kg_per_100_portions"], "кг/100 порций")
        if not intensity["complete"]:
            fact("Кг на 100 порций только покрытых дней", intensity["covered_kg_per_100_portions"], "кг/100 порций")
        fact("Покрытых дней организаций с взвешиваниями", intensity["covered_days"])
        fact("Всего дней организаций с взвешиваниями", intensity["total_days"])

    if wants_missing:
        tool("missing_reports", "Проверка сдачи отчётов")
        suffix = f" за {missing_month}" if missing_month else " за месяц контроля"
        if missing_items:
            names = []
            status_names = {"draft": "черновик", "submitted": "отправлено", "in_review": "на проверке", "returned": "возвращено", None: "отчёта нет", "missing": "отчёта нет"}
            for item in missing_items[:10]:
                names.append(f"{item.get('organization_name', 'Организация')} — {status_names.get(item.get('status'), item.get('status') or 'отчёта нет')}")
            chunks.append(f"Без принятого отчёта{suffix}: {len(missing_items)}. " + "; ".join(names) + ".")
        else:
            chunks.append(f"Все доступные организации имеют принятый отчёт{suffix}.")
        fact("Без принятого отчёта", len(missing_items))

    if wants_trend:
        tool("period_comparison", "Сравнение равных периодов")
        comparison = dashboard["comparison"]
        if comparison["change_percent"] is None:
            chunks.append("В предыдущем периоде нет ненулевой известной массы для процентного сравнения. Это не подтверждает отсутствие отходов: возможно, отчёты ещё не приняты.")
        else:
            delta = comparison["change_percent"]
            trend = "увеличилась" if delta > 0 else "снизилась" if delta < 0 else "не изменилась"
            chunks.append(f"По сравнению с {previous_from} — {previous_to} известная масса {trend}: изменение {_format(delta)}%. Сравнение зависит от полноты принятых отчётов.")
            fact("Изменение к предыдущему периоду", delta, "%")
        fact("Масса предыдущего периода", comparison["previous_mass_kg"], "кг")

    if wants_ecology:
        tool("reference_ecology", "Расчёт по справочным коэффициентам")
        ecology = calculate_ecology(rows)
        if ecology["difference_kg"] is None:
            chunks.append("CO₂ не рассчитан: нет строк с известной массой и обоими коэффициентами. Неизвестные значения не заменяются нулём.")
        else:
            chunks.append(f"Оценка разницы выбросов между ТБО и выбранными способами — {_format(ecology['difference_kg'], 3)} кг CO₂-экв. Формула каждой строки: масса в кг / 1000 × (коэффициент ТБО − коэффициент способа).")
            chunks.append(f"Рассчитано {ecology['calculated_count']} из {ecology['total_count']} строк; покрытие известной массы {_format(ecology['coverage_known_mass_pct'])}%. Это ориентировочная оценка обращения с отходами, не полный жизненный цикл и не доказанная экономия внедрения.")
            fact("Разница выбросов по справочнику", ecology["difference_kg"], "кг CO₂-экв.")
            fact("Покрытие известных масс", ecology["coverage_known_mass_pct"], "%")

    if wants_anomaly or wants_recommend:
        tool("isolation_forest", "ML-проверка необычных ежедневных масс")
        anomalies = detect_anomalies(rows, history)
        output["anomalies"] = anomalies["items"]
        output["model"] = anomalies["model"]
        trained = anomalies["training"]["groups_trained"]
        if not trained:
            chunks.append("ML-вывод не сформирован: недостаточно более ранней разнообразной истории либо модель недоступна. Нужно минимум 10 дней по каждой паре организация/вид.")
        elif not anomalies["items"]:
            chunks.append(f"IsolationForest проверил последние 14 дней выбранного периода для {trained} групп; необычные значения не выделены. Это не гарантия отсутствия ошибок.")
        else:
            chunks.append(f"IsolationForest выделил {len(anomalies['items'])} необычных ежедневных значений в конце выбранного периода. Проверяйте первичные записи, единицы и повторные взвешивания.")
            for item in anomalies["items"][:3]:
                chunks.append(f"• {item['date']}, {item['organization_name']}, {item['waste_name']}: {_format(item['mass_kg'])} кг при историческом среднем {_format(item['expected_mean_kg'])} кг.")
        fact("Групп с обученной моделью", trained)
        fact("Выделенных необычных значений", len(anomalies["items"]))

    if wants_economy:
        tool("economy_requirements", "Проверка данных для сценария экономики")
        chunks.append("В журнале отходов нет стоимости часа, CAPEX и OPEX. Откройте «Экономика и экология → Сценарная экономика», задайте количество операций, минуты до/после и затраты. Система отдельно покажет высвобождённые часы, денежную часть эффекта и окупаемость; сейчас эти суммы не выдумываются.")

    if wants_recommend or wants_summary:
        if dashboard["by_type"]:
            largest = dashboard["by_type"][0]
            chunks.append(f"Наибольшая известная масса приходится на «{largest['name']}»: {_format(largest['mass_kg'])} кг. Начните разбор с этого потока и проверьте полноту учёта.")
            fact("Крупнейший поток", largest["name"])
        if dashboard["by_organization"]:
            largest_org = dashboard["by_organization"][0]
            chunks.append(f"Наибольшая абсолютная масса у {largest_org['name']}: {_format(largest_org['mass_kg'])} кг. Абсолютная масса зависит от объёма обслуживания и полноты учёта; она не является рейтингом эффективности.")
        if wants_recommend:
            chunks.append("Для пилота зафиксируйте базовый период, затем измеряйте отходы на одинаковый объём обслуживания. Выбор переработки согласует ответственное лицо; агент не определяет безопасность еды.")

    if not rows:
        chunks.append("Добавьте записи, отправьте месячный отчёт и проведите принятие проверяющим. Черновики и возвращённые отчёты не включаются в общую аналитику.")
    output["answer"] = "\n\n".join(chunks)
    output["suggestions"] = ["Покажи причины отходов", "Сколько кг на 100 порций?", "Сравни с предыдущим периодом", "Объясни расчёт CO₂", "Кто ещё не сдал отчёт?"]
    return output
