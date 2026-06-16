import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import func

from bookkeeper.database import db
from bookkeeper.models import Account, AccountType, Category, Record, RecordType, Tag, MonthlySummary
from bookkeeper.services.account_service import AccountService
from bookkeeper.services.budget_service import BudgetService


class RecordService:

    @staticmethod
    def create_income(account_id, amount, category_id, record_date, note=None, tag_ids=None):
        account = Account.query.get(account_id)
        if not account:
            raise ValueError(f"Account {account_id} not found")
        if account.is_liability:
            raise ValueError("Income should go to an asset account, not a credit card. Use transfer to pay off credit card instead.")

        amount = Decimal(str(amount))
        record = Record(
            record_type=RecordType.INCOME,
            amount=amount,
            account_id=account_id,
            category_id=category_id,
            note=note,
            record_date=record_date,
        )
        if tag_ids:
            record.tags = Tag.query.filter(Tag.id.in_(tag_ids)).all()

        try:
            db.session.add(record)
            AccountService.adjust_balance(account, amount, session=db.session)
            MonthlySummaryService.upsert_summary(record_date.year, record_date.month, category_id, income_delta=amount)
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

        return record

    @staticmethod
    def create_expense(account_id, amount, category_id, record_date, note=None, tag_ids=None):
        account = Account.query.get(account_id)
        if not account:
            raise ValueError(f"Account {account_id} not found")

        amount = Decimal(str(amount))

        if account.is_liability:
            delta = amount
        else:
            delta = -amount

        record = Record(
            record_type=RecordType.EXPENSE,
            amount=amount,
            account_id=account_id,
            category_id=category_id,
            note=note,
            record_date=record_date,
        )
        if tag_ids:
            record.tags = Tag.query.filter(Tag.id.in_(tag_ids)).all()

        budget_warnings = BudgetService.check_budget_before_expense(
            category_id, record_date.year, record_date.month, amount
        )

        try:
            db.session.add(record)
            AccountService.adjust_balance(account, delta, session=db.session)
            MonthlySummaryService.upsert_summary(record_date.year, record_date.month, category_id, expense_delta=amount)
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

        return record, budget_warnings

    @staticmethod
    def create_transfer(from_account_id, to_account_id, amount, record_date, note=None):
        if from_account_id == to_account_id:
            raise ValueError("Cannot transfer to the same account")

        from_account = Account.query.get(from_account_id)
        to_account = Account.query.get(to_account_id)
        if not from_account or not to_account:
            raise ValueError("Account not found")

        amount = Decimal(str(amount))
        transfer_group_id = str(uuid.uuid4())

        from_delta = -amount if not from_account.is_liability else amount
        to_delta = amount if not to_account.is_liability else -amount

        from_record = Record(
            record_type=RecordType.TRANSFER,
            amount=amount,
            account_id=from_account_id,
            target_account_id=to_account_id,
            note=note,
            record_date=record_date,
            transfer_group_id=transfer_group_id,
        )
        to_record = Record(
            record_type=RecordType.TRANSFER,
            amount=amount,
            account_id=to_account_id,
            target_account_id=from_account_id,
            note=note,
            record_date=record_date,
            transfer_group_id=transfer_group_id,
        )

        try:
            db.session.add(from_record)
            db.session.add(to_record)
            AccountService.adjust_balance(from_account, from_delta, session=db.session)
            AccountService.adjust_balance(to_account, to_delta, session=db.session)
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

        return from_record, to_record

    @staticmethod
    def get_record(record_id):
        return Record.query.get(record_id)

    @staticmethod
    def list_records(account_id=None, record_type=None, category_id=None,
                     start_date=None, end_date=None, tag_id=None, page=1, per_page=20):
        query = Record.query
        if account_id:
            query = query.filter_by(account_id=account_id)
        if record_type:
            query = query.filter_by(record_type=RecordType(record_type))
        if category_id:
            query = query.filter_by(category_id=category_id)
        if start_date:
            query = query.filter(Record.record_date >= start_date)
        if end_date:
            query = query.filter(Record.record_date <= end_date)
        if tag_id:
            query = query.filter(Record.tags.any(Tag.id == tag_id))
        return query.order_by(Record.record_date.desc(), Record.id.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )

    @staticmethod
    def delete_record(record_id):
        record = Record.query.get(record_id)
        if not record:
            return False

        try:
            account = Account.query.get(record.account_id)
            if record.record_type == RecordType.INCOME:
                AccountService.adjust_balance(account, -record.amount, session=db.session)
                if record.category_id:
                    MonthlySummaryService.upsert_summary(
                        record.record_date.year, record.record_date.month,
                        record.category_id, income_delta=-record.amount
                    )
            elif record.record_type == RecordType.EXPENSE:
                if account.is_liability:
                    AccountService.adjust_balance(account, -record.amount, session=db.session)
                else:
                    AccountService.adjust_balance(account, record.amount, session=db.session)
                if record.category_id:
                    MonthlySummaryService.upsert_summary(
                        record.record_date.year, record.record_date.month,
                        record.category_id, expense_delta=-record.amount
                    )
            elif record.record_type == RecordType.TRANSFER:
                RecordService._revert_transfer(record, account)

            db.session.delete(record)
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

        return True

    @staticmethod
    def _revert_transfer(record, account):
        group_id = record.transfer_group_id
        if not group_id:
            return
        sibling = Record.query.filter(
            Record.transfer_group_id == group_id,
            Record.id != record.id
        ).first()
        if not sibling:
            return

        from_rec = record if record.id < sibling.id else sibling
        to_rec = sibling if record.id < sibling.id else record

        from_account = Account.query.get(from_rec.account_id)
        to_account = Account.query.get(to_rec.account_id)

        if from_account.is_liability:
            AccountService.adjust_balance(from_account, -record.amount, session=db.session)
        else:
            AccountService.adjust_balance(from_account, record.amount, session=db.session)

        if to_account.is_liability:
            AccountService.adjust_balance(to_account, record.amount, session=db.session)
        else:
            AccountService.adjust_balance(to_account, -record.amount, session=db.session)

        db.session.delete(sibling)


class MonthlySummaryService:

    @staticmethod
    def upsert_summary(year, month, category_id, income_delta=None, expense_delta=None):
        summary = MonthlySummary.query.filter_by(
            year=year, month=month, category_id=category_id
        ).first()

        if not summary:
            summary = MonthlySummary(
                year=year,
                month=month,
                category_id=category_id,
                total_income=Decimal("0"),
                total_expense=Decimal("0"),
            )
            db.session.add(summary)

        if income_delta is not None:
            summary.total_income = (summary.total_income or Decimal("0")) + income_delta
        if expense_delta is not None:
            summary.total_expense = (summary.total_expense or Decimal("0")) + expense_delta
