from datetime import datetime
from enum import Enum as PyEnum
from bookkeeper.database import db


class AccountType(PyEnum):
    CASH = "cash"
    BANK_CARD = "bank_card"
    CREDIT_CARD = "credit_card"


class RecordType(PyEnum):
    INCOME = "income"
    EXPENSE = "expense"
    TRANSFER = "transfer"


class Account(db.Model):
    __tablename__ = "accounts"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False)
    account_type = db.Column(db.Enum(AccountType), nullable=False)
    balance = db.Column(db.Numeric(precision=15, scale=2), default=0, nullable=False)
    credit_limit = db.Column(db.Numeric(precision=15, scale=2), default=0, nullable=True)
    currency = db.Column(db.String(3), default="CNY", nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "account_type": self.account_type.value,
            "balance": str(self.balance),
            "credit_limit": str(self.credit_limit) if self.credit_limit else None,
            "available_balance": str(self.available_balance),
            "currency": self.currency,
            "is_active": self.is_active,
            "is_liability": self.is_liability,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @property
    def is_liability(self):
        return self.account_type == AccountType.CREDIT_CARD

    @property
    def available_balance(self):
        if self.is_liability:
            return self.credit_limit - self.balance
        return self.balance


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(50), nullable=False)
    record_type = db.Column(db.Enum(RecordType), nullable=False)
    icon = db.Column(db.String(50), nullable=True)
    is_system = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (db.UniqueConstraint("name", "record_type", name="uq_category_name_type"),)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "record_type": self.record_type.value,
            "icon": self.icon,
            "is_system": self.is_system,
        }


record_tags = db.Table(
    "record_tags",
    db.Column("record_id", db.Integer, db.ForeignKey("records.id"), primary_key=True),
    db.Column("tag_id", db.Integer, db.ForeignKey("tags.id"), primary_key=True),
)


class Tag(db.Model):
    __tablename__ = "tags"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {"id": self.id, "name": self.name}


class Record(db.Model):
    __tablename__ = "records"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    record_type = db.Column(db.Enum(RecordType), nullable=False)
    amount = db.Column(db.Numeric(precision=15, scale=2), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), nullable=False)
    target_account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), nullable=True)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=True)
    note = db.Column(db.String(500), nullable=True)
    record_date = db.Column(db.Date, nullable=False, index=True)
    transfer_group_id = db.Column(db.String(36), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    account = db.relationship("Account", foreign_keys=[account_id], backref="records")
    target_account = db.relationship("Account", foreign_keys=[target_account_id])
    category = db.relationship("Category", foreign_keys=[category_id])
    tags = db.relationship("Tag", secondary=record_tags, backref=db.backref("records", lazy="dynamic"))

    __table_args__ = (
        db.Index("ix_records_account_date", "account_id", "record_date"),
        db.Index("ix_records_category_date", "category_id", "record_date"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "record_type": self.record_type.value,
            "amount": str(self.amount),
            "account_id": self.account_id,
            "target_account_id": self.target_account_id,
            "category_id": self.category_id,
            "note": self.note,
            "record_date": self.record_date.isoformat(),
            "transfer_group_id": self.transfer_group_id,
            "tags": [t.to_dict() for t in self.tags],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class Budget(db.Model):
    __tablename__ = "budgets"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False, unique=True)
    amount = db.Column(db.Numeric(precision=15, scale=2), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    month = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    category = db.relationship("Category", foreign_keys=[category_id])

    __table_args__ = (
        db.UniqueConstraint("category_id", "year", "month", name="uq_budget_category_month"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "category_id": self.category_id,
            "category_name": self.category.name if self.category else None,
            "amount": str(self.amount),
            "year": self.year,
            "month": self.month,
            "created_at": self.created_at.isoformat(),
        }


class MonthlySummary(db.Model):
    __tablename__ = "monthly_summaries"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    year = db.Column(db.Integer, nullable=False)
    month = db.Column(db.Integer, nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False)
    total_income = db.Column(db.Numeric(precision=15, scale=2), default=0, nullable=False)
    total_expense = db.Column(db.Numeric(precision=15, scale=2), default=0, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    category = db.relationship("Category", foreign_keys=[category_id])

    __table_args__ = (
        db.UniqueConstraint("year", "month", "category_id", name="uq_monthly_summary"),
        db.Index("ix_summary_year_month", "year", "month"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "year": self.year,
            "month": self.month,
            "category_id": self.category_id,
            "category_name": self.category.name if self.category else None,
            "total_income": str(self.total_income),
            "total_expense": str(self.total_expense),
        }
