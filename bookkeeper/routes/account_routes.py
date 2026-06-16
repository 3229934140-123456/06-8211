from datetime import date
from flask import Blueprint, request, jsonify
from bookkeeper.services.account_service import AccountService

account_bp = Blueprint("accounts", __name__, url_prefix="/api/accounts")


@account_bp.route("", methods=["POST"])
def create_account():
    data = request.get_json()
    try:
        account = AccountService.create_account(
            name=data["name"],
            account_type=data["account_type"],
            initial_balance=data.get("initial_balance"),
            credit_limit=data.get("credit_limit"),
            currency=data.get("currency", "CNY"),
        )
        return jsonify(account.to_dict()), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@account_bp.route("", methods=["GET"])
def list_accounts():
    active_only = request.args.get("active_only", "true").lower() == "true"
    accounts = AccountService.list_accounts(active_only=active_only)
    return jsonify([a.to_dict() for a in accounts])


@account_bp.route("/<int:account_id>", methods=["GET"])
def get_account(account_id):
    account = AccountService.get_account(account_id)
    if not account:
        return jsonify({"error": "Account not found"}), 404
    return jsonify(account.to_dict())


@account_bp.route("/<int:account_id>", methods=["PUT"])
def update_account(account_id):
    data = request.get_json()
    account = AccountService.update_account(account_id, **data)
    if not account:
        return jsonify({"error": "Account not found"}), 404
    return jsonify(account.to_dict())


@account_bp.route("/<int:account_id>", methods=["DELETE"])
def delete_account(account_id):
    if AccountService.delete_account(account_id):
        return jsonify({"message": "Account deactivated"})
    return jsonify({"error": "Account not found"}), 404
