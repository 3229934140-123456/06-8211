from flask import Blueprint, request, jsonify
from bookkeeper.services.stats_service import StatsService

stats_bp = Blueprint("stats", __name__, url_prefix="/api/stats")


@stats_bp.route("/category-summary", methods=["GET"])
def category_summary():
    year = request.args.get("year", type=int)
    month = request.args.get("month", type=int)
    if not year or not month:
        return jsonify({"error": "year and month are required"}), 400
    result = StatsService.category_summary(year, month)
    return jsonify(result)


@stats_bp.route("/annual", methods=["GET"])
def annual_view():
    year = request.args.get("year", type=int)
    if not year:
        return jsonify({"error": "year is required"}), 400
    account_id = request.args.get("account_id", type=int)
    category_id = request.args.get("category_id", type=int)
    result = StatsService.annual_view(
        year,
        account_id=account_id if account_id else None,
        category_id=category_id if category_id else None,
    )
    return jsonify(result)


@stats_bp.route("/monthly-trend", methods=["GET"])
def monthly_trend():
    start_year = request.args.get("start_year", type=int)
    start_month = request.args.get("start_month", type=int)
    end_year = request.args.get("end_year", type=int)
    end_month = request.args.get("end_month", type=int)
    if not all([start_year, start_month, end_year, end_month]):
        return jsonify({"error": "start_year, start_month, end_year, end_month are required"}), 400
    result = StatsService.monthly_trend(start_year, start_month, end_year, end_month)
    return jsonify(result)


@stats_bp.route("/overview", methods=["GET"])
def account_overview():
    result = StatsService.account_overview()
    return jsonify(result)


@stats_bp.route("/expense-ranking", methods=["GET"])
def expense_ranking():
    year = request.args.get("year", type=int)
    month = request.args.get("month", type=int)
    limit = request.args.get("limit", 10, type=int)
    if not year or not month:
        return jsonify({"error": "year and month are required"}), 400
    result = StatsService.expense_ranking(year, month, limit)
    return jsonify(result)
