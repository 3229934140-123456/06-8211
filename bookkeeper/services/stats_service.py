from decimal import Decimal

from sqlalchemy import func

from bookkeeper.database import db
from bookkeeper.models import Account, Category, Record, RecordType, MonthlySummary


class StatsService:

    @staticmethod
    def category_summary(year, month):
        summaries = MonthlySummary.query.filter_by(year=year, month=month).all()
        total_income = Decimal("0")
        total_expense = Decimal("0")
        categories = []
        for s in summaries:
            total_income += s.total_income or Decimal("0")
            total_expense += s.total_expense or Decimal("0")
            categories.append({
                "category_id": s.category_id,
                "category_name": s.category.name if s.category else None,
                "total_income": str(s.total_income),
                "total_expense": str(s.total_expense),
            })
        return {
            "year": year,
            "month": month,
            "total_income": str(total_income),
            "total_expense": str(total_expense),
            "net": str(total_income - total_expense),
            "categories": categories,
        }

    @staticmethod
    def annual_view(year, account_id=None, category_id=None, tag_id=None,
                    start_date=None, end_date=None):
        if account_id or tag_id or start_date or end_date:
            return StatsService._annual_view_from_records(
                year, account_id, category_id, tag_id, start_date, end_date
            )

        query = MonthlySummary.query.filter_by(year=year)
        if category_id:
            query = query.filter_by(category_id=category_id)
        summaries = query.order_by(MonthlySummary.month, MonthlySummary.category_id).all()

        monthly_data = {}
        filtered_categories = set()
        for s in summaries:
            filtered_categories.add(s.category_id)
            key = s.month
            if key not in monthly_data:
                monthly_data[key] = {
                    "year": s.year,
                    "month": s.month,
                    "total_income": Decimal("0"),
                    "total_expense": Decimal("0"),
                    "categories": {},
                }
            monthly_data[key]["total_income"] += s.total_income or Decimal("0")
            monthly_data[key]["total_expense"] += s.total_expense or Decimal("0")
            monthly_data[key]["categories"][s.category_id] = {
                "category_id": s.category_id,
                "category_name": s.category.name if s.category else None,
                "total_income": str(s.total_income),
                "total_expense": str(s.total_expense),
            }

        return StatsService._build_annual_result(
            year, account_id, category_id, tag_id, start_date, end_date,
            monthly_data, filtered_categories
        )

    @staticmethod
    def _annual_view_from_records(year, account_id, category_id, tag_id,
                                  start_date, end_date):
        from datetime import date as _date
        jan1 = _date(year, 1, 1)
        dec31 = _date(year, 12, 31)
        q_start = start_date if start_date and start_date > jan1 else jan1
        q_end = end_date if end_date and end_date < dec31 else dec31

        query = Record.query.filter(
            Record.record_date >= q_start,
            Record.record_date <= q_end,
            Record.record_type.in_([RecordType.INCOME, RecordType.EXPENSE]),
        )
        if account_id:
            query = query.filter_by(account_id=account_id)
        if category_id:
            query = query.filter_by(category_id=category_id)
        if tag_id:
            query = query.filter(Record.tags.any(id=tag_id))

        records = query.all()

        monthly_data = {}
        filtered_categories = set()
        for r in records:
            month = r.record_date.month
            cat_id = r.category_id
            if cat_id:
                filtered_categories.add(cat_id)

            if month not in monthly_data:
                monthly_data[month] = {
                    "year": year,
                    "month": month,
                    "total_income": Decimal("0"),
                    "total_expense": Decimal("0"),
                    "categories": {},
                }

            if cat_id and cat_id not in monthly_data[month]["categories"]:
                monthly_data[month]["categories"][cat_id] = {
                    "category_id": cat_id,
                    "category_name": r.category.name if r.category else None,
                    "total_income": "0",
                    "total_expense": "0",
                }

            if r.record_type == RecordType.INCOME:
                monthly_data[month]["total_income"] += r.amount
                if cat_id:
                    monthly_data[month]["categories"][cat_id]["total_income"] = str(
                        Decimal(monthly_data[month]["categories"][cat_id]["total_income"]) + r.amount
                    )
            elif r.record_type == RecordType.EXPENSE:
                monthly_data[month]["total_expense"] += r.amount
                if cat_id:
                    monthly_data[month]["categories"][cat_id]["total_expense"] = str(
                        Decimal(monthly_data[month]["categories"][cat_id]["total_expense"]) + r.amount
                    )

        return StatsService._build_annual_result(
            year, account_id, category_id, tag_id, start_date, end_date,
            monthly_data, filtered_categories
        )

    @staticmethod
    def _build_annual_result(year, account_id, category_id, tag_id,
                             start_date, end_date, monthly_data, filtered_categories):
        months = []
        year_total_income = Decimal("0")
        year_total_expense = Decimal("0")
        for m in range(1, 13):
            d = monthly_data.get(m)
            if d:
                inc = d["total_income"]
                exp = d["total_expense"]
                year_total_income += inc
                year_total_expense += exp
                months.append({
                    "year": d["year"],
                    "month": d["month"],
                    "total_income": str(inc),
                    "total_expense": str(exp),
                    "net": str(inc - exp),
                    "categories": list(d["categories"].values()),
                })
            else:
                months.append({
                    "year": year,
                    "month": m,
                    "total_income": "0",
                    "total_expense": "0",
                    "net": "0",
                    "categories": [],
                })

        cat_details = []
        for cat_id in sorted(filtered_categories):
            cat = Category.query.get(cat_id)
            cat_inc = Decimal("0")
            cat_exp = Decimal("0")
            for m_data in monthly_data.values():
                c_data = m_data["categories"].get(cat_id)
                if c_data:
                    cat_inc += Decimal(c_data["total_income"])
                    cat_exp += Decimal(c_data["total_expense"])
            cat_details.append({
                "category_id": cat_id,
                "category_name": cat.name if cat else None,
                "year_total_income": str(cat_inc),
                "year_total_expense": str(cat_exp),
            })

        return {
            "year": year,
            "filter": {
                "account_id": account_id,
                "category_id": category_id,
                "tag_id": tag_id,
                "start_date": start_date.isoformat() if start_date else None,
                "end_date": end_date.isoformat() if end_date else None,
            },
            "year_total_income": str(year_total_income),
            "year_total_expense": str(year_total_expense),
            "year_net": str(year_total_income - year_total_expense),
            "months": months,
            "category_totals": cat_details,
        }

    @staticmethod
    def monthly_trend(start_year, start_month, end_year, end_month):
        query = MonthlySummary.query.filter(
            (MonthlySummary.year > start_year) | (
                (MonthlySummary.year == start_year) & (MonthlySummary.month >= start_month)
            ),
            (MonthlySummary.year < end_year) | (
                (MonthlySummary.year == end_year) & (MonthlySummary.month <= end_month)
            ),
        ).order_by(MonthlySummary.year, MonthlySummary.month)

        summaries = query.all()

        monthly_data = {}
        for s in summaries:
            key = f"{s.year}-{s.month:02d}"
            if key not in monthly_data:
                monthly_data[key] = {
                    "year": s.year,
                    "month": s.month,
                    "total_income": Decimal("0"),
                    "total_expense": Decimal("0"),
                }
            monthly_data[key]["total_income"] += s.total_income or Decimal("0")
            monthly_data[key]["total_expense"] += s.total_expense or Decimal("0")

        result = []
        for key in sorted(monthly_data.keys()):
            d = monthly_data[key]
            d["total_income"] = str(d["total_income"])
            d["total_expense"] = str(d["total_expense"])
            d["net"] = str(Decimal(d["total_income"]) - Decimal(d["total_expense"]))
            result.append(d)

        return {
            "start": f"{start_year}-{start_month:02d}",
            "end": f"{end_year}-{end_month:02d}",
            "months": result,
        }

    @staticmethod
    def account_overview():
        accounts = Account.query.filter_by(is_active=True).all()
        total_assets = Decimal("0")
        total_liabilities = Decimal("0")
        account_details = []

        for acc in accounts:
            if acc.is_liability:
                total_liabilities += acc.balance
            else:
                total_assets += acc.balance
            account_details.append({
                "id": acc.id,
                "name": acc.name,
                "type": acc.account_type.value,
                "balance": str(acc.balance),
                "available_balance": str(acc.available_balance),
                "is_liability": acc.is_liability,
            })

        return {
            "total_assets": str(total_assets),
            "total_liabilities": str(total_liabilities),
            "net_worth": str(total_assets - total_liabilities),
            "accounts": account_details,
        }

    @staticmethod
    def expense_ranking(year, month, limit=10):
        summaries = (
            MonthlySummary.query.filter_by(year=year, month=month)
            .order_by(MonthlySummary.total_expense.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "category_id": s.category_id,
                "category_name": s.category.name if s.category else None,
                "total_expense": str(s.total_expense),
            }
            for s in summaries
        ]

    @staticmethod
    def category_drilldown(year, category_id=None, account_id=None,
                           tag_id=None, start_date=None, end_date=None):
        from datetime import date as _date
        jan1 = _date(year, 1, 1)
        dec31 = _date(year, 12, 31)
        q_start = start_date if start_date and start_date > jan1 else jan1
        q_end = end_date if end_date and end_date < dec31 else dec31

        query = Record.query.filter(
            Record.record_date >= q_start,
            Record.record_date <= q_end,
            Record.record_type.in_([RecordType.INCOME, RecordType.EXPENSE]),
        )
        if category_id:
            query = query.filter_by(category_id=category_id)
        if account_id:
            query = query.filter_by(account_id=account_id)
        if tag_id:
            query = query.filter(Record.tags.any(id=tag_id))

        records = query.all()

        year_totals = {}
        monthly_by_category = {}
        for r in records:
            cat_id = r.category_id
            if not cat_id:
                continue
            month = r.record_date.month

            if cat_id not in year_totals:
                year_totals[cat_id] = {
                    "category_id": cat_id,
                    "category_name": r.category.name if r.category else None,
                    "total_income": Decimal("0"),
                    "total_expense": Decimal("0"),
                }
                monthly_by_category[cat_id] = {m: {"income": Decimal("0"), "expense": Decimal("0")} for m in range(1, 13)}

            if r.record_type == RecordType.INCOME:
                year_totals[cat_id]["total_income"] += r.amount
                monthly_by_category[cat_id][month]["income"] += r.amount
            elif r.record_type == RecordType.EXPENSE:
                year_totals[cat_id]["total_expense"] += r.amount
                monthly_by_category[cat_id][month]["expense"] += r.amount

        categories = []
        for cat_id, totals in sorted(year_totals.items(),
                                      key=lambda x: x[1]["total_expense"], reverse=True):
            months = []
            for m in range(1, 13):
                md = monthly_by_category[cat_id][m]
                months.append({
                    "month": m,
                    "income": str(md["income"]),
                    "expense": str(md["expense"]),
                    "net": str(md["income"] - md["expense"]),
                })
            categories.append({
                "category_id": cat_id,
                "category_name": totals["category_name"],
                "year_total_income": str(totals["total_income"]),
                "year_total_expense": str(totals["total_expense"]),
                "year_net": str(totals["total_income"] - totals["total_expense"]),
                "months": months,
            })

        all_year_income = sum((t["total_income"] for t in year_totals.values()), Decimal("0"))
        all_year_expense = sum((t["total_expense"] for t in year_totals.values()), Decimal("0"))

        return {
            "year": year,
            "filter": {
                "category_id": category_id,
                "account_id": account_id,
                "tag_id": tag_id,
                "start_date": start_date.isoformat() if start_date else None,
                "end_date": end_date.isoformat() if end_date else None,
            },
            "year_total_income": str(all_year_income),
            "year_total_expense": str(all_year_expense),
            "year_net": str(all_year_income - all_year_expense),
            "categories": categories,
        }
