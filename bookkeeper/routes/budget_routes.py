from decimal import Decimal, InvalidOperation
from flask import Blueprint, request, jsonify
from bookkeeper.services.budget_service import BudgetService

budget_bp = Blueprint("budgets", __name__, url_prefix="/api/budgets")


def _validate_amount(amount_raw):
    try:
        val = Decimal(str(amount_raw))
    except (InvalidOperation, TypeError, ValueError):
        return None, f"Invalid amount: {amount_raw!r}. Must be a positive number."
    if val <= 0:
        return None, f"Amount must be greater than 0, got {val}"
    return val, None


@budget_bp.route("", methods=["POST"])
def create_budget():
    data = request.get_json()
    amount, err = _validate_amount(data.get("amount"))
    if err:
        return jsonify({"error": err}), 400
    try:
        budget = BudgetService.create_budget(
            category_id=data["category_id"],
            amount=amount,
            year=data["year"],
            month=data["month"],
        )
        return jsonify(budget.to_dict()), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@budget_bp.route("", methods=["GET"])
def list_budgets():
    year = request.args.get("year", type=int)
    month = request.args.get("month", type=int)
    if not year or not month:
        return jsonify({"error": "year and month are required"}), 400
    budgets = BudgetService.list_budgets(year, month)
    return jsonify([b.to_dict() for b in budgets])


@budget_bp.route("/<int:budget_id>", methods=["PUT"])
def update_budget(budget_id):
    data = request.get_json()
    if "amount" in data:
        amount, err = _validate_amount(data["amount"])
        if err:
            return jsonify({"error": err}), 400
        data["amount"] = amount
    budget = BudgetService.update_budget(budget_id, **data)
    if not budget:
        return jsonify({"error": "Budget not found"}), 404
    return jsonify(budget.to_dict())


@budget_bp.route("/<int:budget_id>", methods=["DELETE"])
def delete_budget(budget_id):
    if BudgetService.delete_budget(budget_id):
        return jsonify({"message": "Budget deleted"})
    return jsonify({"error": "Budget not found"}), 404


@budget_bp.route("/status", methods=["GET"])
def budget_status():
    year = request.args.get("year", type=int)
    month = request.args.get("month", type=int)
    if not year or not month:
        return jsonify({"error": "year and month are required"}), 400
    status = BudgetService.get_budget_status(year, month)
    return jsonify(status)
