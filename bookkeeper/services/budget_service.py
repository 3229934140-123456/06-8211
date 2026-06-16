from decimal import Decimal

from sqlalchemy.exc import IntegrityError

from bookkeeper.database import db
from bookkeeper.models import Budget, MonthlySummary


class BudgetService:

    @staticmethod
    def create_budget(category_id, amount, year, month):
        amount = Decimal(str(amount))
        existing = Budget.query.filter_by(
            category_id=category_id, year=year, month=month
        ).first()
        if existing:
            raise ValueError(
                f"Budget already exists for category_id={category_id}, "
                f"year={year}, month={month}"
            )
        budget = Budget(
            category_id=category_id,
            amount=amount,
            year=year,
            month=month,
        )
        try:
            db.session.add(budget)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            raise ValueError(
                f"Budget already exists for category_id={category_id}, "
                f"year={year}, month={month}"
            )
        except Exception:
            db.session.rollback()
            raise
        return budget

    @staticmethod
    def copy_from_month(src_year, src_month, dst_year, dst_month):
        src_budgets = Budget.query.filter_by(year=src_year, month=src_month).all()
        if not src_budgets:
            raise ValueError(f"No budgets found for {src_year}-{src_month:02d}")

        existing_dst = Budget.query.filter_by(year=dst_year, month=dst_month).all()
        existing_cats = {b.category_id for b in existing_dst}

        copied = []
        skipped = []

        for src in src_budgets:
            cat_id = src.category_id
            cat_name = src.category.name if src.category else None
            if cat_id in existing_cats:
                skipped.append({
                    "category_id": cat_id,
                    "category_name": cat_name,
                    "amount": str(src.amount),
                    "reason": "Budget already exists for this category in target month",
                })
                continue

            new_budget = Budget(
                category_id=cat_id,
                amount=src.amount,
                year=dst_year,
                month=dst_month,
            )
            db.session.add(new_budget)
            copied.append({
                "category_id": cat_id,
                "category_name": cat_name,
                "amount": str(src.amount),
            })

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

        return {
            "source": f"{src_year}-{src_month:02d}",
            "target": f"{dst_year}-{dst_month:02d}",
            "copied_count": len(copied),
            "skipped_count": len(skipped),
            "copied": copied,
            "skipped": skipped,
        }

    @staticmethod
    def update_budget(budget_id, amount=None):
        budget = Budget.query.get(budget_id)
        if not budget:
            return None
        if amount is not None:
            budget.amount = Decimal(str(amount))
        db.session.commit()
        return budget

    @staticmethod
    def delete_budget(budget_id):
        budget = Budget.query.get(budget_id)
        if not budget:
            return False
        db.session.delete(budget)
        db.session.commit()
        return True

    @staticmethod
    def list_budgets(year, month):
        return Budget.query.filter_by(year=year, month=month).all()

    @staticmethod
    def get_budget_status(year, month):
        budgets = Budget.query.filter_by(year=year, month=month).all()
        result = []
        for budget in budgets:
            summary = MonthlySummary.query.filter_by(
                year=year, month=month, category_id=budget.category_id
            ).first()
            spent = summary.total_expense if summary else Decimal("0")
            remaining = budget.amount - spent
            overspent = spent > budget.amount
            result.append({
                "budget_id": budget.id,
                "category_id": budget.category_id,
                "category_name": budget.category.name if budget.category else None,
                "budget_amount": str(budget.amount),
                "spent": str(spent),
                "remaining": str(remaining),
                "overspent": overspent,
                "usage_percent": float(spent / budget.amount * 100) if budget.amount > 0 else 0,
            })
        return result

    @staticmethod
    def check_budget_before_expense(category_id, year, month, new_amount):
        with db.session.no_autoflush:
            budget = Budget.query.filter_by(
                category_id=category_id, year=year, month=month
            ).first()

            if not budget:
                return []

            summary = MonthlySummary.query.filter_by(
                year=year, month=month, category_id=category_id
            ).first()

        current_spent = summary.total_expense if summary else Decimal("0")
        projected_spent = current_spent + new_amount
        warnings = []

        if projected_spent > budget.amount:
            over_amount = projected_spent - budget.amount
            warnings.append({
                "type": "budget_exceeded",
                "category_id": category_id,
                "budget_amount": str(budget.amount),
                "current_spent": str(current_spent),
                "new_expense": str(new_amount),
                "projected_spent": str(projected_spent),
                "over_amount": str(over_amount),
                "message": (
                    f"Budget exceeded for category {category_id}: "
                    f"budget={budget.amount}, spent+new={projected_spent}, "
                    f"over by {over_amount}"
                ),
            })
        elif projected_spent > budget.amount * Decimal("0.8"):
            warnings.append({
                "type": "budget_warning",
                "category_id": category_id,
                "budget_amount": str(budget.amount),
                "current_spent": str(current_spent),
                "new_expense": str(new_amount),
                "projected_spent": str(projected_spent),
                "usage_percent": float(projected_spent / budget.amount * 100),
                "message": (
                    f"Budget usage over 80% for category {category_id}: "
                    f"projected={projected_spent}, budget={budget.amount}"
                ),
            })

        return warnings
