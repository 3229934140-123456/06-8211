from decimal import Decimal
from bookkeeper.database import db
from bookkeeper.models import Account, AccountType


class AccountService:

    @staticmethod
    def create_account(name, account_type, initial_balance=None, credit_limit=None, currency="CNY"):
        at = AccountType(account_type)
        account = Account(
            name=name,
            account_type=at,
            currency=currency,
        )
        if initial_balance is not None:
            account.balance = Decimal(str(initial_balance))
        if credit_limit is not None:
            account.credit_limit = Decimal(str(credit_limit))
        if at == AccountType.CREDIT_CARD and account.credit_limit is None:
            account.credit_limit = Decimal("0")
        db.session.add(account)
        db.session.commit()
        return account

    @staticmethod
    def get_account(account_id):
        return Account.query.get(account_id)

    @staticmethod
    def list_accounts(active_only=True):
        query = Account.query
        if active_only:
            query = query.filter_by(is_active=True)
        return query.order_by(Account.id).all()

    @staticmethod
    def update_account(account_id, **kwargs):
        account = Account.query.get(account_id)
        if not account:
            return None
        for key in ("name", "currency"):
            if key in kwargs and kwargs[key] is not None:
                setattr(account, key, kwargs[key])
        if "credit_limit" in kwargs and kwargs["credit_limit"] is not None:
            account.credit_limit = Decimal(str(kwargs["credit_limit"]))
        if "is_active" in kwargs:
            account.is_active = kwargs["is_active"]
        db.session.commit()
        return account

    @staticmethod
    def delete_account(account_id):
        account = Account.query.get(account_id)
        if not account:
            return False
        account.is_active = False
        db.session.commit()
        return True

    @staticmethod
    def adjust_balance(account, delta, session=None):
        sess = session or db.session
        locked_account = sess.query(Account).with_for_update().filter_by(id=account.id).first()
        if locked_account is None:
            raise ValueError(f"Account {account.id} not found")
        new_balance = locked_account.balance + delta
        if locked_account.is_liability:
            if new_balance > locked_account.credit_limit:
                raise ValueError(
                    f"Credit card expense exceeds credit limit: "
                    f"current balance={locked_account.balance}, "
                    f"delta={delta}, credit_limit={locked_account.credit_limit}"
                )
        else:
            if new_balance < 0:
                raise ValueError(
                    f"Insufficient balance: current={locked_account.balance}, delta={delta}"
                )
        locked_account.balance = new_balance
        return locked_account
