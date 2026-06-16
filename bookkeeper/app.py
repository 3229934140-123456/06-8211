import os
from flask import Flask
from bookkeeper.database import db
from bookkeeper.models import AccountType, RecordType, Category
from bookkeeper.routes.account_routes import account_bp
from bookkeeper.routes.record_routes import record_bp
from bookkeeper.routes.budget_routes import budget_bp
from bookkeeper.routes.stats_routes import stats_bp


def create_app(config=None):
    app = Flask(__name__)

    db_path = os.environ.get("BOOKKEEPER_DB_PATH", "bookkeeper.db")
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    if config:
        app.config.update(config)

    db.init_app(app)

    app.register_blueprint(account_bp)
    app.register_blueprint(record_bp)
    app.register_blueprint(budget_bp)
    app.register_blueprint(stats_bp)

    with app.app_context():
        db.create_all()
        _seed_default_categories()

    return app


def _seed_default_categories():
    if Category.query.first() is not None:
        return

    expense_categories = [
        ("餐饮", "utensils"), ("交通", "car"), ("购物", "shopping-cart"),
        ("住房", "home"), ("娱乐", "gamepad"), ("医疗", "heartbeat"),
        ("教育", "graduation-cap"), ("通讯", "phone"), ("服饰", "tshirt"),
        ("日用品", "basket"), ("其他支出", "ellipsis-h"),
    ]
    income_categories = [
        ("工资", "money-bill"), ("奖金", "gift"), ("投资收益", "chart-line"),
        ("兼职", "briefcase"), ("其他收入", "ellipsis-h"),
    ]

    for name, icon in expense_categories:
        db.session.add(Category(name=name, record_type=RecordType.EXPENSE, icon=icon, is_system=True))
    for name, icon in income_categories:
        db.session.add(Category(name=name, record_type=RecordType.INCOME, icon=icon, is_system=True))

    db.session.commit()


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, port=5000)
