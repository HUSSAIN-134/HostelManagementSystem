"""REST API for the Hostel Accommodation and Student Services system."""

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from functools import wraps

import mysql.connector
from mysql.connector import errorcode
from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import HTTPException

from database import get_connection

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False


class ApiError(Exception):
    def __init__(self, message, status=400, details=None):
        self.message = message
        self.status = status
        self.details = details


def json_safe(value):
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def error_response(message, status, details=None):
    payload = {"error": message}
    if details:
        payload["details"] = details
    return jsonify(payload), status


@app.errorhandler(ApiError)
def handle_api_error(exc):
    return error_response(exc.message, exc.status, exc.details)


@app.errorhandler(HTTPException)
def handle_http_error(exc):
    return error_response(exc.description, exc.code or 500)


@app.errorhandler(mysql.connector.Error)
def handle_database_error(exc):
    code = getattr(exc, "errno", None)
    if code == errorcode.ER_DUP_ENTRY:
        message = str(exc)
        if "registration_no" in message:
            return error_response("Registration number already exists.", 409)
        if "email" in message:
            return error_response("Email address already exists.", 409)
        if "uq_one_active_allocation_bed" in message or "active_bed_id" in message:
            return error_response("Bed is already occupied.", 409)
        if "uq_one_active_allocation_student" in message or "active_student_id" in message:
            return error_response("Student already has an active allocation.", 409)
        return error_response("A record with a unique value already exists.", 409)
    if code == errorcode.ER_NO_REFERENCED_ROW_2:
        return error_response("A referenced student, user, room, bed, fee, or allocation does not exist.", 400)
    if code == errorcode.ER_ROW_IS_REFERENCED_2:
        return error_response("This record is in use and cannot be deleted.", 409)
    if code == errorcode.ER_CHECK_CONSTRAINT_VIOLATED:
        return error_response("Input violates a database validation rule (for example, date or amount range).", 400)
    if code == 1644:
        message = str(exc)
        if "occup" in message.lower() or "bed" in message.lower():
            return error_response("Bed is occupied or room capacity would be exceeded.", 409)
        if "gender" in message.lower():
            return error_response("Student does not meet this block's gender policy.", 400)
        if "fee" in message.lower() or "payment" in message.lower():
            return error_response("Payment exceeds the applicable fee balance.", 400)
        return error_response("The requested operation violates a database business rule.", 400)
    if code in (errorcode.ER_ACCESS_DENIED_ERROR, errorcode.CR_CONNECTION_ERROR, errorcode.CR_CONN_HOST_ERROR):
        app.logger.error("MySQL connection/authentication failure: %s", exc)
        return error_response("Database connection failed. Check MYSQL_HOST, MYSQL_USER, MYSQL_PASSWORD, and MYSQL_DATABASE.", 503)
    app.logger.exception("Unhandled MySQL error", exc_info=exc)
    return error_response("Database operation failed.", 500)


@app.errorhandler(Exception)
def handle_unexpected_error(exc):
    app.logger.exception("Unhandled application error", exc_info=exc)
    return error_response("Internal server error.", 500)


def db_operation(fn):
    """Open and close one connection/cursor for an endpoint operation."""
    @wraps(fn)
    def wrapped(*args, **kwargs):
        connection = None
        cursor = None
        try:
            connection = get_connection()
            cursor = connection.cursor(dictionary=True)
            return fn(cursor, connection, *args, **kwargs)
        except ApiError:
            if connection and connection.in_transaction:
                connection.rollback()
            raise
        except mysql.connector.Error:
            if connection and connection.in_transaction:
                connection.rollback()
            raise
        except Exception:
            if connection and connection.in_transaction:
                connection.rollback()
            raise
        finally:
            if cursor:
                cursor.close()
            if connection and connection.is_connected():
                connection.close()
    return wrapped


def body_object():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ApiError("Request body must be a JSON object.", 400)
    return data


def validate_fields(data, required, allowed):
    missing = [field for field in required if field not in data or data[field] is None or data[field] == ""]
    unknown = sorted(set(data) - set(allowed))
    if missing:
        raise ApiError("Missing required fields.", 400, {"fields": missing})
    if unknown:
        raise ApiError("Unknown fields in request.", 400, {"fields": unknown})


def positive_id(value, field="id"):
    try:
        result = int(value)
    except (TypeError, ValueError):
        raise ApiError(f"{field} must be a positive integer.", 400)
    if result <= 0:
        raise ApiError(f"{field} must be a positive integer.", 400)
    return result


def parse_date(value, field, allow_datetime=False):
    if isinstance(value, (date, datetime)):
        return value
    if not isinstance(value, str) or not value.strip():
        raise ApiError(f"{field} must be a valid ISO date.", 400)
    try:
        if allow_datetime and len(value.strip()) > 10:
            return datetime.fromisoformat(value)
        return date.fromisoformat(value)
    except ValueError:
        raise ApiError(f"{field} must be a valid ISO date/time.", 400)


def require_text(data, fields):
    for field in fields:
        if field in data and (not isinstance(data[field], str) or not data[field].strip()):
            raise ApiError(f"{field} must be a non-empty string.", 400)


def validate_boolean_fields(data, fields):
    for field in fields:
        if field in data and data[field] not in (True, False, 0, 1):
            raise ApiError(f"{field} must be a boolean.", 400)
        if field in data:
            data[field] = bool(data[field])


def fetch_all(cursor, sql, params=()):
    cursor.execute(sql, params)
    return json_safe(cursor.fetchall())


def fetch_one(cursor, sql, params=()):
    cursor.execute(sql, params)
    row = cursor.fetchone()
    return json_safe(row) if row else None


def insert_record(cursor, table, fields, data):
    """Build an INSERT only from fixed, code-defined identifiers; values stay bound."""
    columns = [field for field in fields if field in data]
    sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join(['%s'] * len(columns))})"
    cursor.execute(sql, tuple(data[field] for field in columns))
    return cursor.lastrowid


def update_record(cursor, table, id_column, record_id, fields, data):
    columns = [field for field in fields if field in data]
    if not columns:
        raise ApiError("Provide at least one field to update.", 400)
    assignments = ", ".join(f"{column}=%s" for column in columns)
    cursor.execute(f"UPDATE {table} SET {assignments} WHERE {id_column}=%s", tuple(data[column] for column in columns) + (record_id,))
    if cursor.rowcount == 0:
        exists = fetch_one(cursor, f"SELECT {id_column} FROM {table} WHERE {id_column}=%s", (record_id,))
        if not exists:
            raise ApiError("Record not found.", 404)


def require_enum(data, field, allowed, required=True):
    if field not in data:
        if required:
            raise ApiError(f"{field} is required.", 400)
        return
    if data[field] not in allowed:
        raise ApiError(f"{field} must be one of: {', '.join(allowed)}.", 400)


def maybe_date_fields(data, fields):
    for field in fields:
        if field in data and data[field] is not None:
            data[field] = parse_date(data[field], field, allow_datetime=True)


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/health")
@db_operation
def health(cursor, connection):
    cursor.execute("SELECT 1 AS database_ok")
    cursor.fetchone()
    return jsonify({"status": "ok", "database": "connected"}), 200


@app.get("/api/stats")
@db_operation
def stats(cursor, connection):
    tables = ("students", "users", "hostel_blocks", "rooms", "beds", "allocations", "transfers", "payments", "visitors", "complaints", "maintenance_requests", "vacating_records")
    result = {}
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) AS count FROM {table}")
        result[table] = cursor.fetchone()["count"]
    cursor.execute("SELECT COUNT(*) AS count FROM allocations WHERE status='ACTIVE'")
    result["active_allocations"] = cursor.fetchone()["count"]
    return jsonify(result)


# Students
STUDENT_FIELDS = ("user_id", "registration_no", "first_name", "last_name", "email", "phone", "gender", "date_of_birth", "department", "course", "year_of_study", "emergency_contact_name", "emergency_contact_phone")
STUDENT_REQUIRED = ("registration_no", "first_name", "last_name", "email", "phone", "gender", "department", "course", "year_of_study", "emergency_contact_name", "emergency_contact_phone")
STUDENT_SQL = "SELECT student_id,user_id,registration_no,first_name,last_name,email,phone,gender,date_of_birth,department,course,year_of_study,emergency_contact_name,emergency_contact_phone,created_at FROM students"


@app.get("/api/students")
@db_operation
def list_students(cursor, connection):
    return jsonify(fetch_all(cursor, STUDENT_SQL + " ORDER BY student_id"))


@app.get("/api/students/<int:student_id>")
@db_operation
def get_student(cursor, connection, student_id):
    row = fetch_one(cursor, STUDENT_SQL + " WHERE student_id=%s", (positive_id(student_id),))
    if not row:
        raise ApiError("Student not found.", 404)
    return jsonify(row)


@app.post("/api/students")
@db_operation
def create_student(cursor, connection):
    data = body_object()
    validate_fields(data, STUDENT_REQUIRED, STUDENT_FIELDS)
    require_text(data, tuple(field for field in STUDENT_REQUIRED if field != "year_of_study"))
    require_enum(data, "gender", ("MALE", "FEMALE", "OTHER"))
    try:
        data["year_of_study"] = int(data["year_of_study"])
        if not 1 <= data["year_of_study"] <= 8:
            raise ValueError
    except (TypeError, ValueError):
        raise ApiError("year_of_study must be an integer from 1 to 8.", 400)
    if data.get("date_of_birth"):
        data["date_of_birth"] = parse_date(data["date_of_birth"], "date_of_birth")
    student_id = insert_record(cursor, "students", STUDENT_FIELDS, data)
    connection.commit()
    return jsonify(fetch_one(cursor, STUDENT_SQL + " WHERE student_id=%s", (student_id,))), 201


@app.put("/api/students/<int:student_id>")
@db_operation
def update_student(cursor, connection, student_id):
    record_id = positive_id(student_id, "student_id")
    data = body_object()
    validate_fields(data, (), STUDENT_FIELDS)
    require_text(data, [field for field in STUDENT_REQUIRED if field in data and field != "year_of_study"])
    if "gender" in data:
        require_enum(data, "gender", ("MALE", "FEMALE", "OTHER"))
    if "year_of_study" in data:
        try:
            data["year_of_study"] = int(data["year_of_study"])
            if not 1 <= data["year_of_study"] <= 8:
                raise ValueError
        except (TypeError, ValueError):
            raise ApiError("year_of_study must be an integer from 1 to 8.", 400)
    if data.get("date_of_birth"):
        data["date_of_birth"] = parse_date(data["date_of_birth"], "date_of_birth")
    update_record(cursor, "students", "student_id", record_id, STUDENT_FIELDS, data)
    connection.commit()
    return jsonify(fetch_one(cursor, STUDENT_SQL + " WHERE student_id=%s", (record_id,)))


@app.delete("/api/students/<int:student_id>")
@db_operation
def delete_student(cursor, connection, student_id):
    cursor.execute("DELETE FROM students WHERE student_id=%s", (positive_id(student_id, "student_id"),))
    if cursor.rowcount == 0:
        raise ApiError("Student not found.", 404)
    connection.commit()
    return jsonify({"message": "Student deleted."})


# Blocks
BLOCK_FIELDS = ("block_code", "block_name", "gender_policy", "address", "warden_user_id", "is_active")
BLOCK_REQUIRED = ("block_code", "block_name", "gender_policy")
BLOCK_SQL = "SELECT block_id,block_code,block_name,gender_policy,address,warden_user_id,is_active,created_at FROM hostel_blocks"


@app.get("/api/blocks")
@db_operation
def list_blocks(cursor, connection):
    return jsonify(fetch_all(cursor, BLOCK_SQL + " ORDER BY block_id"))


@app.post("/api/blocks")
@db_operation
def create_block(cursor, connection):
    data = body_object(); validate_fields(data, BLOCK_REQUIRED, BLOCK_FIELDS); require_text(data, BLOCK_REQUIRED)
    require_enum(data, "gender_policy", ("MALE", "FEMALE", "MIXED"))
    validate_boolean_fields(data, ("is_active",))
    block_id = insert_record(cursor, "hostel_blocks", BLOCK_FIELDS, data); connection.commit()
    return jsonify(fetch_one(cursor, BLOCK_SQL + " WHERE block_id=%s", (block_id,))), 201


@app.put("/api/blocks/<int:block_id>")
@db_operation
def update_block(cursor, connection, block_id):
    record_id = positive_id(block_id, "block_id"); data = body_object(); validate_fields(data, (), BLOCK_FIELDS)
    require_text(data, [field for field in BLOCK_REQUIRED if field in data])
    if "gender_policy" in data: require_enum(data, "gender_policy", ("MALE", "FEMALE", "MIXED"))
    validate_boolean_fields(data, ("is_active",))
    update_record(cursor, "hostel_blocks", "block_id", record_id, BLOCK_FIELDS, data); connection.commit()
    return jsonify(fetch_one(cursor, BLOCK_SQL + " WHERE block_id=%s", (record_id,)))


@app.delete("/api/blocks/<int:block_id>")
@db_operation
def delete_block(cursor, connection, block_id):
    cursor.execute("DELETE FROM hostel_blocks WHERE block_id=%s", (positive_id(block_id, "block_id"),))
    if cursor.rowcount == 0: raise ApiError("Hostel block not found.", 404)
    connection.commit(); return jsonify({"message": "Hostel block deleted."})


# Rooms
ROOM_FIELDS = ("block_id", "room_number", "floor_number", "capacity", "room_type", "is_active")
ROOM_REQUIRED = ("block_id", "room_number", "capacity")
ROOM_SQL = "SELECT room_id,block_id,room_number,floor_number,capacity,room_type,is_active FROM rooms"


@app.get("/api/rooms")
@db_operation
def list_rooms(cursor, connection):
    sql = "SELECT r.room_id,r.block_id,b.block_code,b.block_name,r.room_number,r.floor_number,r.capacity,r.room_type,r.is_active,COUNT(DISTINCT bd.bed_id) AS bed_count,COUNT(DISTINCT a.allocation_id) AS occupied_beds FROM rooms r JOIN hostel_blocks b ON b.block_id=r.block_id LEFT JOIN beds bd ON bd.room_id=r.room_id AND bd.is_active=TRUE LEFT JOIN allocations a ON a.bed_id=bd.bed_id AND a.status='ACTIVE' GROUP BY r.room_id,r.block_id,b.block_code,b.block_name,r.room_number,r.floor_number,r.capacity,r.room_type,r.is_active ORDER BY r.room_id"
    return jsonify(fetch_all(cursor, sql))


@app.get("/api/rooms/<int:room_id>")
@db_operation
def get_room(cursor, connection, room_id):
    row = fetch_one(cursor, ROOM_SQL + " WHERE room_id=%s", (positive_id(room_id, "room_id"),))
    if not row: raise ApiError("Room not found.", 404)
    return jsonify(row)


@app.post("/api/rooms")
@db_operation
def create_room(cursor, connection):
    data = body_object(); validate_fields(data, ROOM_REQUIRED, ROOM_FIELDS)
    data["block_id"] = positive_id(data["block_id"], "block_id")
    try: data["capacity"] = int(data["capacity"])
    except (TypeError, ValueError): raise ApiError("capacity must be an integer.", 400)
    if not 1 <= data["capacity"] <= 12: raise ApiError("capacity must be between 1 and 12.", 400)
    if "room_type" in data: require_enum(data, "room_type", ("STANDARD", "DELUXE", "ACCESSIBLE"))
    validate_boolean_fields(data, ("is_active",))
    require_text(data, ("room_number",))
    room_id = insert_record(cursor, "rooms", ROOM_FIELDS, data); connection.commit()
    return jsonify(fetch_one(cursor, ROOM_SQL + " WHERE room_id=%s", (room_id,))), 201


@app.put("/api/rooms/<int:room_id>")
@db_operation
def update_room(cursor, connection, room_id):
    record_id = positive_id(room_id, "room_id"); data = body_object(); validate_fields(data, (), ROOM_FIELDS)
    if "block_id" in data: data["block_id"] = positive_id(data["block_id"], "block_id")
    if "capacity" in data:
        try: data["capacity"] = int(data["capacity"])
        except (TypeError, ValueError): raise ApiError("capacity must be an integer.", 400)
        if not 1 <= data["capacity"] <= 12: raise ApiError("capacity must be between 1 and 12.", 400)
    if "room_type" in data: require_enum(data, "room_type", ("STANDARD", "DELUXE", "ACCESSIBLE"))
    validate_boolean_fields(data, ("is_active",))
    update_record(cursor, "rooms", "room_id", record_id, ROOM_FIELDS, data); connection.commit()
    return jsonify(fetch_one(cursor, ROOM_SQL + " WHERE room_id=%s", (record_id,)))


@app.delete("/api/rooms/<int:room_id>")
@db_operation
def delete_room(cursor, connection, room_id):
    cursor.execute("DELETE FROM rooms WHERE room_id=%s", (positive_id(room_id, "room_id"),))
    if cursor.rowcount == 0: raise ApiError("Room not found.", 404)
    connection.commit(); return jsonify({"message": "Room deleted."})


# Beds
BED_FIELDS = ("room_id", "bed_label", "is_active")


@app.get("/api/beds")
@db_operation
def list_beds(cursor, connection):
    sql = "SELECT be.bed_id,be.room_id,r.room_number,h.block_code,be.bed_label,be.is_active,CASE WHEN a.allocation_id IS NULL THEN FALSE ELSE TRUE END AS is_occupied FROM beds be JOIN rooms r ON r.room_id=be.room_id JOIN hostel_blocks h ON h.block_id=r.block_id LEFT JOIN allocations a ON a.bed_id=be.bed_id AND a.status='ACTIVE' ORDER BY h.block_code,r.room_number,be.bed_label"
    return jsonify(fetch_all(cursor, sql))


@app.get("/api/beds/available")
@db_operation
def available_beds(cursor, connection):
    sql = "SELECT bed_id,bed_label,room_number,block_code,block_name FROM v_vacant_beds ORDER BY block_code,room_number,bed_label"
    return jsonify(fetch_all(cursor, sql))


@app.post("/api/beds")
@db_operation
def create_bed(cursor, connection):
    data = body_object(); validate_fields(data, ("room_id", "bed_label"), BED_FIELDS)
    data["room_id"] = positive_id(data["room_id"], "room_id"); require_text(data, ("bed_label",))
    validate_boolean_fields(data, ("is_active",))
    bed_id = insert_record(cursor, "beds", BED_FIELDS, data); connection.commit()
    return jsonify(fetch_one(cursor, "SELECT bed_id,room_id,bed_label,is_active FROM beds WHERE bed_id=%s", (bed_id,))), 201


@app.put("/api/beds/<int:bed_id>")
@db_operation
def update_bed(cursor, connection, bed_id):
    record_id = positive_id(bed_id, "bed_id"); data = body_object(); validate_fields(data, (), BED_FIELDS)
    if "room_id" in data: data["room_id"] = positive_id(data["room_id"], "room_id")
    require_text(data, ["bed_label"] if "bed_label" in data else ())
    validate_boolean_fields(data, ("is_active",))
    update_record(cursor, "beds", "bed_id", record_id, BED_FIELDS, data); connection.commit()
    return jsonify(fetch_one(cursor, "SELECT bed_id,room_id,bed_label,is_active FROM beds WHERE bed_id=%s", (record_id,)))


# Allocations and transfers
ALLOCATION_JOIN = "SELECT a.allocation_id,a.student_id,s.registration_no,s.first_name,s.last_name,a.bed_id,b.bed_label,r.room_id,r.room_number,h.block_id,h.block_code,h.block_name,a.allocation_date,a.expected_vacate_date,a.actual_vacate_date,a.status,a.created_by,a.created_at FROM allocations a JOIN students s ON s.student_id=a.student_id JOIN beds b ON b.bed_id=a.bed_id JOIN rooms r ON r.room_id=b.room_id JOIN hostel_blocks h ON h.block_id=r.block_id"


@app.get("/api/allocations")
@db_operation
def list_allocations(cursor, connection):
    return jsonify(fetch_all(cursor, ALLOCATION_JOIN + " ORDER BY a.allocation_date DESC,a.allocation_id DESC"))


@app.get("/api/allocations/<int:allocation_id>")
@db_operation
def get_allocation(cursor, connection, allocation_id):
    row = fetch_one(cursor, ALLOCATION_JOIN + " WHERE a.allocation_id=%s", (positive_id(allocation_id, "allocation_id"),))
    if not row: raise ApiError("Allocation not found.", 404)
    return jsonify(row)


@app.post("/api/allocations")
@db_operation
def create_allocation(cursor, connection):
    data = body_object(); allowed = ("student_id", "bed_id", "allocation_date", "expected_vacate_date", "created_by")
    validate_fields(data, ("student_id", "bed_id", "allocation_date", "expected_vacate_date"), allowed)
    sid = positive_id(data["student_id"], "student_id"); bid = positive_id(data["bed_id"], "bed_id")
    creator_id = positive_id(data["created_by"], "created_by") if data.get("created_by") is not None else None
    alloc_date = parse_date(data["allocation_date"], "allocation_date"); expected = parse_date(data["expected_vacate_date"], "expected_vacate_date")
    if expected < alloc_date: raise ApiError("expected_vacate_date cannot be earlier than allocation_date.", 400)
    connection.start_transaction()
    student = fetch_one(cursor, "SELECT student_id,gender FROM students WHERE student_id=%s FOR UPDATE", (sid,))
    if not student: raise ApiError("Student not found.", 404)
    bed = fetch_one(cursor, "SELECT be.bed_id,be.room_id,be.is_active,r.capacity,r.is_active AS room_active,h.is_active AS block_active,h.gender_policy FROM beds be JOIN rooms r ON r.room_id=be.room_id JOIN hostel_blocks h ON h.block_id=r.block_id WHERE be.bed_id=%s FOR UPDATE", (bid,))
    if not bed or not bed["is_active"] or not bed["room_active"] or not bed["block_active"]: raise ApiError("Bed, room, or block is invalid or inactive.", 400)
    fetch_one(cursor, "SELECT room_id FROM rooms WHERE room_id=%s FOR UPDATE", (bed["room_id"],))
    if bed["gender_policy"] != "MIXED" and bed["gender_policy"] != student["gender"]: raise ApiError("Student does not meet this block's gender policy.", 400)
    occupied = fetch_one(cursor, "SELECT allocation_id FROM allocations WHERE bed_id=%s AND status='ACTIVE' FOR UPDATE", (bid,))
    if occupied: raise ApiError("Bed is already occupied.", 409)
    active = fetch_one(cursor, "SELECT allocation_id FROM allocations WHERE student_id=%s AND status='ACTIVE' FOR UPDATE", (sid,))
    if active: raise ApiError("Student already has an active allocation.", 409)
    cursor.execute("SELECT COUNT(*) AS active_count FROM allocations a JOIN beds be ON be.bed_id=a.bed_id WHERE be.room_id=%s AND a.status='ACTIVE'", (bed["room_id"],))
    if cursor.fetchone()["active_count"] >= bed["capacity"]: raise ApiError("Room capacity is full.", 409)
    data = {"student_id": sid, "bed_id": bid, "allocation_date": alloc_date, "expected_vacate_date": expected}
    if creator_id is not None: data["created_by"] = creator_id
    allocation_id = insert_record(cursor, "allocations", ("student_id", "bed_id", "allocation_date", "expected_vacate_date", "created_by"), data)
    connection.commit()
    return jsonify(fetch_one(cursor, ALLOCATION_JOIN + " WHERE a.allocation_id=%s", (allocation_id,))), 201


@app.get("/api/transfers")
@db_operation
def list_transfers(cursor, connection):
    sql = "SELECT t.transfer_id,fa.student_id,s.registration_no,t.from_allocation_id,t.to_allocation_id,t.transfer_date,t.reason,t.approved_by,t.created_at FROM transfers t JOIN allocations fa ON fa.allocation_id=t.from_allocation_id JOIN students s ON s.student_id=fa.student_id ORDER BY t.transfer_date DESC,t.transfer_id DESC"
    return jsonify(fetch_all(cursor, sql))


@app.post("/api/transfers")
@db_operation
def create_transfer(cursor, connection):
    data = body_object(); allowed = ("student_id", "from_allocation_id", "to_bed_id", "transfer_date", "expected_vacate_date", "reason", "approved_by")
    validate_fields(data, ("student_id", "from_allocation_id", "to_bed_id", "transfer_date", "expected_vacate_date", "reason"), allowed)
    require_text(data, ("reason",))
    if len(data["reason"]) > 500: raise ApiError("reason must be at most 500 characters.", 400)
    sid = positive_id(data["student_id"], "student_id"); old_id = positive_id(data["from_allocation_id"], "from_allocation_id"); new_bed_id = positive_id(data["to_bed_id"], "to_bed_id")
    transfer_date = parse_date(data["transfer_date"], "transfer_date"); expected = parse_date(data["expected_vacate_date"], "expected_vacate_date")
    if expected < transfer_date: raise ApiError("expected_vacate_date cannot be earlier than transfer_date.", 400)
    connection.start_transaction()
    old = fetch_one(cursor, "SELECT allocation_id,student_id,bed_id,allocation_date FROM allocations WHERE allocation_id=%s AND status='ACTIVE' FOR UPDATE", (old_id,))
    if not old or old["student_id"] != sid: raise ApiError("Active allocation for this student was not found.", 404)
    if transfer_date < parse_date(old["allocation_date"], "allocation_date"): raise ApiError("transfer_date cannot precede the original allocation date.", 400)
    student = fetch_one(cursor, "SELECT student_id,gender FROM students WHERE student_id=%s FOR UPDATE", (sid,))
    target = fetch_one(cursor, "SELECT be.bed_id,be.room_id,be.is_active,r.capacity,r.is_active AS room_active,h.is_active AS block_active,h.gender_policy FROM beds be JOIN rooms r ON r.room_id=be.room_id JOIN hostel_blocks h ON h.block_id=r.block_id WHERE be.bed_id=%s FOR UPDATE", (new_bed_id,))
    if not target or not target["is_active"] or not target["room_active"] or not target["block_active"]: raise ApiError("Target bed, room, or block is invalid or inactive.", 400)
    if target["gender_policy"] != "MIXED" and target["gender_policy"] != student["gender"]: raise ApiError("Student does not meet this block's gender policy.", 400)
    fetch_one(cursor, "SELECT room_id FROM rooms WHERE room_id=%s FOR UPDATE", (target["room_id"],))
    if old["bed_id"] == new_bed_id: raise ApiError("Transfer must select a different bed.", 400)
    occupied = fetch_one(cursor, "SELECT allocation_id FROM allocations WHERE bed_id=%s AND status='ACTIVE' FOR UPDATE", (new_bed_id,))
    if occupied: raise ApiError("Target bed is already occupied.", 409)
    cursor.execute("UPDATE allocations SET status='TRANSFERRED',actual_vacate_date=%s WHERE allocation_id=%s", (transfer_date, old_id))
    cursor.execute("SELECT COUNT(*) AS active_count FROM allocations a JOIN beds be ON be.bed_id=a.bed_id WHERE be.room_id=%s AND a.status='ACTIVE'", (target["room_id"],))
    if cursor.fetchone()["active_count"] >= target["capacity"]: raise ApiError("Target room capacity is full.", 409)
    cols = ("student_id", "bed_id", "allocation_date", "expected_vacate_date", "created_by")
    new_data = {"student_id": sid, "bed_id": new_bed_id, "allocation_date": transfer_date, "expected_vacate_date": expected}
    new_allocation_id = insert_record(cursor, "allocations", cols, new_data)
    cursor.execute("INSERT INTO transfers (from_allocation_id,to_allocation_id,transfer_date,reason,approved_by) VALUES (%s,%s,%s,%s,%s)", (old_id, new_allocation_id, transfer_date, data["reason"], positive_id(data["approved_by"], "approved_by") if data.get("approved_by") is not None else None))
    connection.commit()
    transfer_id = cursor.lastrowid
    transfer_row = fetch_one(cursor, "SELECT t.*,a.student_id FROM transfers t JOIN allocations a ON a.allocation_id=t.from_allocation_id WHERE t.transfer_id=%s", (transfer_id,))
    return jsonify({"transfer": transfer_row, "new_allocation": fetch_one(cursor, ALLOCATION_JOIN + " WHERE a.allocation_id=%s", (new_allocation_id,))}), 201


# Fees and payments
FEE_FIELDS = ("academic_year", "term", "fee_type", "amount", "due_date", "is_active")


@app.get("/api/fees")
@db_operation
def list_fees(cursor, connection):
    return jsonify(fetch_all(cursor, "SELECT fee_schedule_id,academic_year,term,fee_type,amount,due_date,is_active,created_at FROM fee_schedules ORDER BY due_date"))


@app.post("/api/fees")
@db_operation
def create_fee(cursor, connection):
    data = body_object(); validate_fields(data, ("academic_year", "term", "fee_type", "amount", "due_date"), FEE_FIELDS)
    require_text(data, ("academic_year", "term")); require_enum(data, "fee_type", ("HOSTEL", "MESS", "SECURITY_DEPOSIT", "OTHER"))
    validate_boolean_fields(data, ("is_active",))
    try: data["amount"] = Decimal(str(data["amount"]))
    except (InvalidOperation, TypeError): raise ApiError("amount must be a valid positive number.", 400)
    if data["amount"] <= 0: raise ApiError("amount must be greater than zero.", 400)
    data["due_date"] = parse_date(data["due_date"], "due_date")
    fee_id = insert_record(cursor, "fee_schedules", FEE_FIELDS, data); connection.commit()
    return jsonify(fetch_one(cursor, "SELECT * FROM fee_schedules WHERE fee_schedule_id=%s", (fee_id,))), 201


@app.get("/api/payments")
@db_operation
def list_payments(cursor, connection):
    sql = "SELECT p.payment_id,p.student_id,s.registration_no,p.fee_schedule_id,f.fee_type,f.academic_year,f.term,p.amount,p.payment_date,p.payment_method,p.transaction_reference,p.received_by,p.notes FROM payments p JOIN students s ON s.student_id=p.student_id JOIN fee_schedules f ON f.fee_schedule_id=p.fee_schedule_id ORDER BY p.payment_date DESC"
    return jsonify(fetch_all(cursor, sql))


@app.post("/api/payments")
@db_operation
def create_payment(cursor, connection):
    fields = ("student_id", "fee_schedule_id", "amount", "payment_date", "payment_method", "transaction_reference", "received_by", "notes")
    data = body_object(); validate_fields(data, ("student_id", "fee_schedule_id", "amount", "payment_method"), fields)
    data["student_id"] = positive_id(data["student_id"], "student_id"); data["fee_schedule_id"] = positive_id(data["fee_schedule_id"], "fee_schedule_id")
    try: data["amount"] = Decimal(str(data["amount"]))
    except (InvalidOperation, TypeError): raise ApiError("amount must be a valid positive number.", 400)
    if data["amount"] <= 0: raise ApiError("amount must be greater than zero.", 400)
    require_enum(data, "payment_method", ("CASH", "CARD", "BANK_TRANSFER", "UPI", "OTHER"))
    if data.get("payment_date") is not None: data["payment_date"] = parse_date(data["payment_date"], "payment_date", allow_datetime=True)
    if data.get("received_by") is not None: data["received_by"] = positive_id(data["received_by"], "received_by")
    payment_id = insert_record(cursor, "payments", fields, data); connection.commit()
    return jsonify(fetch_one(cursor, "SELECT * FROM payments WHERE payment_id=%s", (payment_id,))), 201


# Visitors
VISITOR_FIELDS = ("student_id", "visitor_name", "relationship_to_student", "phone", "purpose", "check_in", "check_out", "approved_by")


@app.get("/api/visitors")
@db_operation
def list_visitors(cursor, connection):
    sql = "SELECT v.visitor_id,v.student_id,s.registration_no,s.first_name,s.last_name,v.visitor_name,v.relationship_to_student,v.phone,v.purpose,v.check_in,v.check_out,v.approved_by FROM visitors v JOIN students s ON s.student_id=v.student_id ORDER BY v.check_in DESC"
    return jsonify(fetch_all(cursor, sql))


@app.post("/api/visitors")
@db_operation
def create_visitor(cursor, connection):
    data = body_object(); validate_fields(data, ("student_id", "visitor_name", "relationship_to_student", "phone", "purpose"), VISITOR_FIELDS)
    data["student_id"] = positive_id(data["student_id"], "student_id"); require_text(data, ("visitor_name", "relationship_to_student", "phone", "purpose"))
    maybe_date_fields(data, ("check_in", "check_out"))
    if data.get("approved_by") is not None: data["approved_by"] = positive_id(data["approved_by"], "approved_by")
    visitor_id = insert_record(cursor, "visitors", VISITOR_FIELDS, data); connection.commit()
    return jsonify(fetch_one(cursor, "SELECT * FROM visitors WHERE visitor_id=%s", (visitor_id,))), 201


@app.put("/api/visitors/<int:visitor_id>/checkout")
@db_operation
def checkout_visitor(cursor, connection, visitor_id):
    record_id = positive_id(visitor_id, "visitor_id"); data = request.get_json(silent=True) or {}
    if not isinstance(data, dict) or set(data) - {"check_out"}: raise ApiError("Body may contain only check_out.", 400)
    checkout = parse_date(data["check_out"], "check_out", allow_datetime=True) if data.get("check_out") else datetime.now()
    cursor.execute("UPDATE visitors SET check_out=%s WHERE visitor_id=%s AND check_out IS NULL", (checkout, record_id))
    if cursor.rowcount == 0:
        row = fetch_one(cursor, "SELECT visitor_id,check_out FROM visitors WHERE visitor_id=%s", (record_id,))
        if not row: raise ApiError("Visitor record not found.", 404)
        raise ApiError("Visitor has already checked out.", 409)
    connection.commit(); return jsonify(fetch_one(cursor, "SELECT * FROM visitors WHERE visitor_id=%s", (record_id,)))


# Complaints
COMPLAINT_FIELDS = ("student_id", "category", "subject", "description", "status", "priority", "resolved_at", "assigned_to")


@app.get("/api/complaints")
@db_operation
def list_complaints(cursor, connection):
    sql = "SELECT c.complaint_id,c.student_id,s.registration_no,c.category,c.subject,c.description,c.status,c.priority,c.submitted_at,c.resolved_at,c.assigned_to FROM complaints c JOIN students s ON s.student_id=c.student_id ORDER BY c.submitted_at DESC"
    return jsonify(fetch_all(cursor, sql))


@app.post("/api/complaints")
@db_operation
def create_complaint(cursor, connection):
    data = body_object(); validate_fields(data, ("student_id", "category", "subject", "description"), COMPLAINT_FIELDS)
    data["student_id"] = positive_id(data["student_id"], "student_id"); require_text(data, ("subject", "description"))
    require_enum(data, "category", ("CLEANLINESS", "FOOD", "NOISE", "SECURITY", "WATER", "ELECTRICAL", "OTHER"))
    if "status" in data: require_enum(data, "status", ("OPEN", "IN_PROGRESS", "RESOLVED", "CLOSED"))
    if "priority" in data: require_enum(data, "priority", ("LOW", "MEDIUM", "HIGH", "URGENT"))
    maybe_date_fields(data, ("resolved_at",))
    if data.get("assigned_to") is not None: data["assigned_to"] = positive_id(data["assigned_to"], "assigned_to")
    complaint_id = insert_record(cursor, "complaints", COMPLAINT_FIELDS, data); connection.commit()
    return jsonify(fetch_one(cursor, "SELECT * FROM complaints WHERE complaint_id=%s", (complaint_id,))), 201


@app.put("/api/complaints/<int:complaint_id>")
@db_operation
def update_complaint(cursor, connection, complaint_id):
    record_id = positive_id(complaint_id, "complaint_id"); data = body_object()
    fields = ("category", "subject", "description", "status", "priority", "resolved_at", "assigned_to")
    validate_fields(data, (), fields)
    if "category" in data: require_enum(data, "category", ("CLEANLINESS", "FOOD", "NOISE", "SECURITY", "WATER", "ELECTRICAL", "OTHER"))
    if "status" in data: require_enum(data, "status", ("OPEN", "IN_PROGRESS", "RESOLVED", "CLOSED"))
    if "priority" in data: require_enum(data, "priority", ("LOW", "MEDIUM", "HIGH", "URGENT"))
    if "subject" in data or "description" in data: require_text(data, [f for f in ("subject", "description") if f in data])
    maybe_date_fields(data, ("resolved_at",))
    if data.get("assigned_to") is not None: data["assigned_to"] = positive_id(data["assigned_to"], "assigned_to")
    update_record(cursor, "complaints", "complaint_id", record_id, fields, data); connection.commit()
    return jsonify(fetch_one(cursor, "SELECT * FROM complaints WHERE complaint_id=%s", (record_id,)))


# Maintenance
MAINTENANCE_FIELDS = ("room_id", "requested_by_student_id", "category", "description", "status", "priority", "completed_at", "assigned_to")


@app.get("/api/maintenance")
@db_operation
def list_maintenance(cursor, connection):
    sql = "SELECT m.maintenance_id,m.room_id,h.block_code,r.room_number,m.requested_by_student_id,s.registration_no,m.category,m.description,m.status,m.priority,m.requested_at,m.completed_at,m.assigned_to FROM maintenance_requests m JOIN rooms r ON r.room_id=m.room_id JOIN hostel_blocks h ON h.block_id=r.block_id LEFT JOIN students s ON s.student_id=m.requested_by_student_id ORDER BY m.requested_at DESC"
    return jsonify(fetch_all(cursor, sql))


@app.post("/api/maintenance")
@db_operation
def create_maintenance(cursor, connection):
    data = body_object(); validate_fields(data, ("room_id", "category", "description"), MAINTENANCE_FIELDS)
    data["room_id"] = positive_id(data["room_id"], "room_id"); require_text(data, ("description",))
    require_enum(data, "category", ("PLUMBING", "ELECTRICAL", "FURNITURE", "CLEANING", "STRUCTURAL", "OTHER"))
    if "status" in data: require_enum(data, "status", ("OPEN", "ASSIGNED", "IN_PROGRESS", "COMPLETED", "CANCELLED"))
    if "priority" in data: require_enum(data, "priority", ("LOW", "MEDIUM", "HIGH", "URGENT"))
    if data.get("requested_by_student_id") is not None: data["requested_by_student_id"] = positive_id(data["requested_by_student_id"], "requested_by_student_id")
    if data.get("assigned_to") is not None: data["assigned_to"] = positive_id(data["assigned_to"], "assigned_to")
    maybe_date_fields(data, ("completed_at",))
    maintenance_id = insert_record(cursor, "maintenance_requests", MAINTENANCE_FIELDS, data); connection.commit()
    return jsonify(fetch_one(cursor, "SELECT * FROM maintenance_requests WHERE maintenance_id=%s", (maintenance_id,))), 201


@app.put("/api/maintenance/<int:maintenance_id>")
@db_operation
def update_maintenance(cursor, connection, maintenance_id):
    record_id = positive_id(maintenance_id, "maintenance_id"); data = body_object()
    fields = ("requested_by_student_id", "category", "description", "status", "priority", "completed_at", "assigned_to")
    validate_fields(data, (), fields)
    if "category" in data: require_enum(data, "category", ("PLUMBING", "ELECTRICAL", "FURNITURE", "CLEANING", "STRUCTURAL", "OTHER"))
    if "status" in data: require_enum(data, "status", ("OPEN", "ASSIGNED", "IN_PROGRESS", "COMPLETED", "CANCELLED"))
    if "priority" in data: require_enum(data, "priority", ("LOW", "MEDIUM", "HIGH", "URGENT"))
    if "description" in data: require_text(data, ("description",))
    for field in ("requested_by_student_id", "assigned_to"):
        if data.get(field) is not None: data[field] = positive_id(data[field], field)
    maybe_date_fields(data, ("completed_at",))
    update_record(cursor, "maintenance_requests", "maintenance_id", record_id, fields, data); connection.commit()
    return jsonify(fetch_one(cursor, "SELECT * FROM maintenance_requests WHERE maintenance_id=%s", (record_id,)))


# Vacating
@app.get("/api/vacating")
@db_operation
def list_vacating(cursor, connection):
    sql = "SELECT v.vacating_id,v.allocation_id,a.student_id,s.registration_no,a.bed_id,b.bed_label,r.room_number,h.block_code,v.vacating_date,v.reason,v.inspection_notes,v.deposit_refund,v.processed_by,v.created_at FROM vacating_records v JOIN allocations a ON a.allocation_id=v.allocation_id JOIN students s ON s.student_id=a.student_id JOIN beds b ON b.bed_id=a.bed_id JOIN rooms r ON r.room_id=b.room_id JOIN hostel_blocks h ON h.block_id=r.block_id ORDER BY v.vacating_date DESC"
    return jsonify(fetch_all(cursor, sql))


@app.post("/api/vacating")
@db_operation
def create_vacating(cursor, connection):
    data = body_object(); allowed = ("allocation_id", "vacating_date", "reason", "inspection_notes", "deposit_refund", "processed_by")
    validate_fields(data, ("allocation_id", "vacating_date", "reason"), allowed); require_text(data, ("reason",))
    allocation_id = positive_id(data["allocation_id"], "allocation_id"); vacate_date = parse_date(data["vacating_date"], "vacating_date")
    try: refund = Decimal(str(data.get("deposit_refund", 0)))
    except (InvalidOperation, TypeError): raise ApiError("deposit_refund must be a non-negative number.", 400)
    if refund < 0: raise ApiError("deposit_refund cannot be negative.", 400)
    if data.get("processed_by") is not None: data["processed_by"] = positive_id(data["processed_by"], "processed_by")
    connection.start_transaction()
    allocation = fetch_one(cursor, "SELECT allocation_id,allocation_date,status FROM allocations WHERE allocation_id=%s FOR UPDATE", (allocation_id,))
    if not allocation: raise ApiError("Allocation not found.", 404)
    if allocation["status"] != "ACTIVE": raise ApiError("Only an active allocation can be vacated.", 409)
    if vacate_date < parse_date(allocation["allocation_date"], "allocation_date"): raise ApiError("vacating_date cannot be earlier than allocation_date.", 400)
    cursor.execute("UPDATE allocations SET status='VACATED',actual_vacate_date=%s WHERE allocation_id=%s", (vacate_date, allocation_id))
    vac_fields = ("allocation_id", "vacating_date", "reason", "inspection_notes", "deposit_refund", "processed_by")
    vac_data = {"allocation_id": allocation_id, "vacating_date": vacate_date, "reason": data["reason"], "deposit_refund": refund}
    if data.get("inspection_notes") is not None: vac_data["inspection_notes"] = data["inspection_notes"]
    if data.get("processed_by") is not None: vac_data["processed_by"] = data["processed_by"]
    vacating_id = insert_record(cursor, "vacating_records", vac_fields, vac_data)
    connection.commit()
    return jsonify(fetch_one(cursor, "SELECT * FROM vacating_records WHERE vacating_id=%s", (vacating_id,))), 201


# Reports
@app.get("/api/reports/occupancy")
@db_operation
def report_occupancy(cursor, connection):
    return jsonify(fetch_all(cursor, "SELECT * FROM v_occupancy ORDER BY block_code,room_number"))


@app.get("/api/reports/vacancies")
@db_operation
def report_vacancies(cursor, connection):
    return jsonify(fetch_all(cursor, "SELECT * FROM v_vacant_beds ORDER BY block_code,room_number,bed_label"))


@app.get("/api/reports/fee-dues")
@db_operation
def report_fee_dues(cursor, connection):
    return jsonify(fetch_all(cursor, "SELECT * FROM v_fee_dues WHERE balance>0 ORDER BY due_date,registration_no,fee_type"))


@app.get("/api/reports/allocation-history")
@db_operation
def report_allocation_history(cursor, connection):
    sql = "SELECT a.allocation_id,a.student_id,s.registration_no,s.first_name,s.last_name,a.bed_id,b.bed_label,r.room_number,h.block_code,a.allocation_date,a.expected_vacate_date,a.actual_vacate_date,a.status,t.transfer_id,t.transfer_date,t.reason AS transfer_reason FROM allocations a JOIN students s ON s.student_id=a.student_id JOIN beds b ON b.bed_id=a.bed_id JOIN rooms r ON r.room_id=b.room_id JOIN hostel_blocks h ON h.block_id=r.block_id LEFT JOIN transfers t ON t.from_allocation_id=a.allocation_id OR t.to_allocation_id=a.allocation_id ORDER BY s.registration_no,a.allocation_date,a.allocation_id"
    return jsonify(fetch_all(cursor, sql))


@app.get("/api/reports/visitors")
@db_operation
def report_visitors(cursor, connection):
    sql = "SELECT v.visitor_id,v.student_id,s.registration_no,s.first_name,s.last_name,v.visitor_name,v.relationship_to_student,v.phone,v.purpose,v.check_in,v.check_out,v.approved_by FROM visitors v JOIN students s ON s.student_id=v.student_id ORDER BY v.check_in DESC"
    return jsonify(fetch_all(cursor, sql))


@app.get("/api/reports/complaints")
@db_operation
def report_complaints(cursor, connection):
    sql = "SELECT c.complaint_id,c.student_id,s.registration_no,c.category,c.subject,c.description,c.status,c.priority,c.submitted_at,c.resolved_at,c.assigned_to FROM complaints c JOIN students s ON s.student_id=c.student_id WHERE c.status IN ('OPEN','IN_PROGRESS') ORDER BY FIELD(c.priority,'URGENT','HIGH','MEDIUM','LOW'),c.submitted_at"
    return jsonify(fetch_all(cursor, sql))


@app.get("/api/reports/maintenance")
@db_operation
def report_maintenance(cursor, connection):
    sql = "SELECT m.maintenance_id,m.room_id,h.block_code,r.room_number,m.requested_by_student_id,m.category,m.description,m.status,m.priority,m.requested_at,m.completed_at,m.assigned_to FROM maintenance_requests m JOIN rooms r ON r.room_id=m.room_id JOIN hostel_blocks h ON h.block_id=r.block_id ORDER BY m.requested_at DESC"
    return jsonify(fetch_all(cursor, sql))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
