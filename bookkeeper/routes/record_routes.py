from datetime import date
from decimal import Decimal, InvalidOperation
from io import StringIO
import csv

from flask import Blueprint, request, jsonify, Response
from bookkeeper.database import db
from bookkeeper.models import Category, RecordType, Tag
from bookkeeper.services.record_service import RecordService

record_bp = Blueprint("records", __name__, url_prefix="/api/records")


def _validate_amount(amount_raw):
    if isinstance(amount_raw, float) and (amount_raw != amount_raw or amount_raw == float("inf") or amount_raw == float("-inf")):
        return None, f"Invalid amount: {amount_raw!r}. Must be a positive finite number."
    try:
        val = Decimal(str(amount_raw))
    except (InvalidOperation, TypeError, ValueError):
        return None, f"Invalid amount: {amount_raw!r}. Must be a positive finite number."
    if not val.is_finite():
        return None, f"Invalid amount: {amount_raw!r}. Must be a positive finite number."
    if val <= 0:
        return None, f"Amount must be greater than 0, got {val}"
    return val, None


def _validate_category_type(category_id, expected_type):
    cat = Category.query.get(category_id)
    if not cat:
        return None, f"Category {category_id} not found"
    if cat.record_type != expected_type:
        return None, (
            f"Category type mismatch: category '{cat.name}' is of type "
            f"'{cat.record_type.value}', but expected '{expected_type.value}'"
        )
    return cat, None


@record_bp.route("/categories", methods=["POST"])
def create_category():
    data = request.get_json()
    cat = Category(
        name=data["name"],
        record_type=RecordType(data["record_type"]),
        icon=data.get("icon"),
    )
    try:
        db.session.add(cat)
        db.session.commit()
        return jsonify(cat.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400


@record_bp.route("/categories", methods=["GET"])
def list_categories():
    record_type = request.args.get("record_type")
    query = Category.query
    if record_type:
        query = query.filter_by(record_type=RecordType(record_type))
    return jsonify([c.to_dict() for c in query.all()])


@record_bp.route("/tags", methods=["POST"])
def create_tag():
    data = request.get_json()
    tag = Tag(name=data["name"])
    try:
        db.session.add(tag)
        db.session.commit()
        return jsonify(tag.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400


@record_bp.route("/tags", methods=["GET"])
def list_tags():
    return jsonify([t.to_dict() for t in Tag.query.all()])


@record_bp.route("/income", methods=["POST"])
def create_income():
    data = request.get_json()
    amount, err = _validate_amount(data.get("amount"))
    if err:
        return jsonify({"error": err}), 400
    cat, err = _validate_category_type(data["category_id"], RecordType.INCOME)
    if err:
        return jsonify({"error": err}), 400
    try:
        record_date = date.fromisoformat(data["record_date"])
        record = RecordService.create_income(
            account_id=data["account_id"],
            amount=amount,
            category_id=data["category_id"],
            record_date=record_date,
            note=data.get("note"),
            tag_ids=data.get("tag_ids"),
        )
        return jsonify(record.to_dict()), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@record_bp.route("/expense", methods=["POST"])
def create_expense():
    data = request.get_json()
    amount, err = _validate_amount(data.get("amount"))
    if err:
        return jsonify({"error": err}), 400
    cat, err = _validate_category_type(data["category_id"], RecordType.EXPENSE)
    if err:
        return jsonify({"error": err}), 400
    try:
        record_date = date.fromisoformat(data["record_date"])
        record, warnings = RecordService.create_expense(
            account_id=data["account_id"],
            amount=amount,
            category_id=data["category_id"],
            record_date=record_date,
            note=data.get("note"),
            tag_ids=data.get("tag_ids"),
        )
        result = record.to_dict()
        result["budget_warnings"] = warnings
        return jsonify(result), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@record_bp.route("/transfer", methods=["POST"])
def create_transfer():
    data = request.get_json()
    amount, err = _validate_amount(data.get("amount"))
    if err:
        return jsonify({"error": err}), 400
    try:
        record_date = date.fromisoformat(data["record_date"])
        from_record, to_record = RecordService.create_transfer(
            from_account_id=data["from_account_id"],
            to_account_id=data["to_account_id"],
            amount=amount,
            record_date=record_date,
            note=data.get("note"),
        )
        return jsonify({
            "from_record": from_record.to_dict(),
            "to_record": to_record.to_dict(),
        }), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@record_bp.route("", methods=["GET"])
def list_records():
    try:
        pagination = RecordService.list_records(
            account_id=request.args.get("account_id", type=int),
            record_type=request.args.get("record_type"),
            category_id=request.args.get("category_id", type=int),
            start_date=date.fromisoformat(request.args["start_date"]) if "start_date" in request.args else None,
            end_date=date.fromisoformat(request.args["end_date"]) if "end_date" in request.args else None,
            tag_id=request.args.get("tag_id", type=int),
            page=request.args.get("page", 1, type=int),
            per_page=request.args.get("per_page", 20, type=int),
        )
        return jsonify({
            "items": [r.to_dict() for r in pagination.items],
            "total": pagination.total,
            "page": pagination.page,
            "per_page": pagination.per_page,
            "pages": pagination.pages,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@record_bp.route("/<int:record_id>", methods=["GET"])
def get_record(record_id):
    record = RecordService.get_record(record_id)
    if not record:
        return jsonify({"error": "Record not found"}), 404
    return jsonify(record.to_dict())


@record_bp.route("/<int:record_id>", methods=["DELETE"])
def delete_record(record_id):
    if RecordService.delete_record(record_id):
        return jsonify({"message": "Record deleted"})
    return jsonify({"error": "Record not found"}), 404


@record_bp.route("/export/csv", methods=["GET"])
def export_csv():
    try:
        records = RecordService.query_records(
            account_id=request.args.get("account_id", type=int),
            record_type=request.args.get("record_type"),
            category_id=request.args.get("category_id", type=int),
            start_date=date.fromisoformat(request.args["start_date"]) if "start_date" in request.args else None,
            end_date=date.fromisoformat(request.args["end_date"]) if "end_date" in request.args else None,
            tag_id=request.args.get("tag_id", type=int),
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "id", "date", "direction", "type", "amount",
        "account_id", "target_account_id", "category_id",
        "note", "tags",
    ])
    for r in records:
        tag_names = ",".join(t.name for t in r.tags)
        writer.writerow([
            r.id,
            r.record_date.isoformat(),
            r.direction,
            r.record_type.value,
            str(r.amount),
            r.account_id,
            r.target_account_id or "",
            r.category_id or "",
            r.note or "",
            tag_names,
        ])

    filename = "records_export.csv"
    return Response(
        output.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
