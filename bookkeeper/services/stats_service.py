from decimal import Decimal

from sqlalchemy import func

from bookkeeper.database import db
from bookkeeper.models import Account, Record, RecordType, MonthlySummary


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
