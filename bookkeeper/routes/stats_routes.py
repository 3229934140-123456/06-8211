from datetime import date
from io import StringIO
import csv

from flask import Blueprint, request, jsonify, Response
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
    tag_id = request.args.get("tag_id", type=int)
    start_date = None
    end_date = None
    try:
        if "start_date" in request.args:
            start_date = date.fromisoformat(request.args["start_date"])
        if "end_date" in request.args:
            end_date = date.fromisoformat(request.args["end_date"])
    except ValueError as e:
        return jsonify({"error": f"Invalid date: {e}"}), 400

    result = StatsService.annual_view(
        year,
        account_id=account_id if account_id else None,
        category_id=category_id if category_id else None,
        tag_id=tag_id if tag_id else None,
        start_date=start_date,
        end_date=end_date,
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


@stats_bp.route("/category-drilldown", methods=["GET"])
def category_drilldown():
    year = request.args.get("year", type=int)
    if not year:
        return jsonify({"error": "year is required"}), 400
    category_id = request.args.get("category_id", type=int)
    account_id = request.args.get("account_id", type=int)
    tag_id = request.args.get("tag_id", type=int)
    start_date = None
    end_date = None
    try:
        if "start_date" in request.args:
            start_date = date.fromisoformat(request.args["start_date"])
        if "end_date" in request.args:
            end_date = date.fromisoformat(request.args["end_date"])
    except ValueError as e:
        return jsonify({"error": f"Invalid date: {e}"}), 400

    result = StatsService.category_drilldown(
        year,
        category_id=category_id if category_id else None,
        account_id=account_id if account_id else None,
        tag_id=tag_id if tag_id else None,
        start_date=start_date,
        end_date=end_date,
    )
    return jsonify(result)


@stats_bp.route("/annual/export/csv", methods=["GET"])
def export_annual_csv():
    year = request.args.get("year", type=int)
    if not year:
        return jsonify({"error": "year is required"}), 400
    account_id = request.args.get("account_id", type=int)
    category_id = request.args.get("category_id", type=int)
    tag_id = request.args.get("tag_id", type=int)
    start_date = None
    end_date = None
    try:
        if "start_date" in request.args:
            start_date = date.fromisoformat(request.args["start_date"])
        if "end_date" in request.args:
            end_date = date.fromisoformat(request.args["end_date"])
    except ValueError as e:
        return jsonify({"error": f"Invalid date: {e}"}), 400

    data = StatsService.annual_view(
        year,
        account_id=account_id if account_id else None,
        category_id=category_id if category_id else None,
        tag_id=tag_id if tag_id else None,
        start_date=start_date,
        end_date=end_date,
    )

    output = StringIO()
    writer = csv.writer(output)

    writer.writerow([f"# Annual Report - {year}"])
    writer.writerow([f"# Filters: account_id={account_id or 'ALL'}, category_id={category_id or 'ALL'}, tag_id={tag_id or 'ALL'}, start_date={start_date.isoformat() if start_date else 'ALL'}, end_date={end_date.isoformat() if end_date else 'ALL'}"])
    writer.writerow([f"# Summary: year_total_income={data['year_total_income']}, year_total_expense={data['year_total_expense']}, year_net={data['year_net']}"])
    writer.writerow([])

    writer.writerow(["month", "total_income", "total_expense", "net"])
    for m in data["months"]:
        writer.writerow([
            m["month"],
            m["total_income"],
            m["total_expense"],
            m["net"],
        ])
    writer.writerow([])
    writer.writerow(["# Category totals for the year"])
    writer.writerow(["category_id", "category_name", "year_total_income", "year_total_expense"])
    for ct in data["category_totals"]:
        writer.writerow([
            ct["category_id"],
            ct["category_name"],
            ct["year_total_income"],
            ct["year_total_expense"],
        ])

    writer.writerow([])
    writer.writerow(["# Monthly breakdown by category"])
    writer.writerow(["month", "category_id", "category_name", "total_income", "total_expense"])
    for m in data["months"]:
        for c in m["categories"]:
            writer.writerow([
                m["month"],
                c["category_id"],
                c["category_name"],
                c["total_income"],
                c["total_expense"],
            ])

    filename = f"annual_report_{year}.csv"
    return Response(
        output.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
