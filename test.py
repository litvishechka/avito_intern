import os
import psycopg2
from flask import Flask, request, jsonify

app = Flask(__name__)
username = os.getenv("POSTGRES_USERNAME")
password = os.getenv("POSTGRES_PASSWORD")
host = os.getenv("POSTGRES_HOST")
port = os.getenv("POSTGRES_PORT")
dbname = os.getenv("POSTGRES_DATABASE")

def get_db_connection():
    conn_url = f"postgresql://{username}:{password}@{host}:{port}/{dbname}"

    conn = psycopg2.connect(conn_url)
    return conn


def create_tables():
    commands = (
        """
        CREATE TYPE tender_status AS ENUM ('Created', 'Published', 'Closed');
        """,
        """
        CREATE TABLE IF NOT EXISTS tender (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            name VARCHAR(255) NOT NULL,
            description TEXT,
            service_type VARCHAR(100),
            status tender_status DEFAULT 'Created',
            version INT DEFAULT 1,
            organization_id UUID REFERENCES organization(id) ON DELETE CASCADE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
    )
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        for command in commands:
            cur.execute(command)
        cur.close()
        conn.commit()
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
    finally:
        if conn is not None:
            conn.close()


@app.route('/api/ping', methods=['GET'])
def ping():
    try:
        conn = get_db_connection()
        conn.close()
        return "ok", 200
    except Exception as e:
        return "Server not ready", 500


@app.route('/api/tenders/new', methods=['POST'])
def create_tender():
    data = request.json
    required_fields = ['name', 'description', 'serviceType', 'organizationId', 'creatorUsername']
    
    for field in required_fields:
        if field not in data:
            return jsonify({"error": f"Missing required field: {field}"}), 400

    name = data['name']
    description = data['description']
    service_type = data['serviceType']
    organization_id = data['organizationId']
    creator_username = data['creatorUsername']
    print(creator_username, flush=True)
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        print(creator_username, flush=True)
        cursor.execute("SELECT id FROM employee WHERE username = %s", (creator_username,))
        user = cursor.fetchone()
        print(user, flush=True)
        if not user:
            return jsonify({"error": "User does not exist"}), 401
        
        cursor.execute('''
            SELECT 1 FROM organization_responsible
            WHERE organization_id = %s AND user_id = %s
        ''', (organization_id, user[0]))
        responsible = cursor.fetchone()
        print(responsible, flush=True)
        if not responsible:
            return jsonify({"error": "User is not responsible for the organization"}), 403
        
        cursor.execute('''
            INSERT INTO tender (name, description, service_type, organization_id)
            VALUES (%s, %s, %s, %s) RETURNING id, created_at
        ''', (name, description, service_type, organization_id))
        
        tender = cursor.fetchone()
        tender_id = tender[0]
        created_at = tender[1]

        conn.commit()

        return jsonify({
            "id": tender_id,
            "name": name,
            "description": description,
            "serviceType": service_type,
            "status": "Created",
            "version": 1,
            "createdAt": created_at
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/api/tenders/<tender_id>/status', methods=['PUT'])
def change_tender_status(tender_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    status = request.args.get('status')
    username = request.args.get('username')
    
    if not status or status not in ['Created', 'Published', 'Closed']:
        return jsonify({"reason": "Invalid status value"}), 400

    if not username:
        return jsonify({"reason": "Username is required"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT id FROM employee WHERE username = %s", (username,))
        user = cursor.fetchone()
        if not user:
            return jsonify({"reason": "User does not exist"}), 401
        
        cursor.execute('''
            SELECT o.id
            FROM tender t
            JOIN organization_responsible o_r ON o_r.organization_id = t.organization_id
            JOIN organization o ON o.id = o_r.organization_id
            WHERE t.id = %s AND o_r.user_id = %s
        ''', (tender_id, user[0]))
        responsible = cursor.fetchone()
        if not responsible:
            return jsonify({"reason": "User is not responsible for the organization"}), 403
        
        cursor.execute('''
            UPDATE tender
            SET status = %s
            WHERE id = %s AND (
                (status = 'Created' AND %s = 'Published') OR
                (status = 'Published' AND %s = 'Closed')
            )
            RETURNING id, name, description, status, service_type, version, created_at
        ''', (status, tender_id, status, status))
        
        tender = cursor.fetchone()
        if not tender:
            return jsonify({"reason": "Tender not found or cannot change status"}), 404

        conn.commit()

        return jsonify({
            "id": tender[0],
            "name": tender[1],
            "description": tender[2],
            "status": tender[3],
            "serviceType": tender[4],
            "version": tender[5],
            "createdAt": tender[6]
        }), 200
    except Exception as e:
        return jsonify({"reason": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/api/tenders/<tender_id>/edit', methods=['PATCH'])
def edit_tender(tender_id):
    data = request.json
    username = request.args.get('username')
    
    if not username:
        return jsonify({"reason": "Username is required"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Проверка существования пользователя
        cursor.execute("SELECT id FROM employee WHERE username = %s", (username,))
        user = cursor.fetchone()
        if not user:
            return jsonify({"reason": "User does not exist"}), 401

        # Проверка прав пользователя
        cursor.execute('''
            SELECT o.id
            FROM tender t
            JOIN organization_responsible o_r ON o_r.organization_id = t.organization_id
            JOIN organization o ON o.id = o_r.organization_id
            WHERE t.id = %s AND o_r.user_id = %s
        ''', (tender_id, user[0]))
        responsible = cursor.fetchone()
        if not responsible:
            return jsonify({"reason": "User is not authorized to edit this tender"}), 403
        
        # Подготовка для обновления тендера
        update_fields = []
        params = []

        if 'name' in data:
            update_fields.append("name = %s")
            params.append(data['name'])
        if 'description' in data:
            update_fields.append("description = %s")
            params.append(data['description'])
        if 'serviceType' in data:
            update_fields.append("service_type = %s")
            params.append(data['serviceType'])
        
        if not update_fields:
            return jsonify({"reason": "No fields provided for update"}), 400
        
        params.append(tender_id)
        
        update_query = f'''
            UPDATE tender
            SET {', '.join(update_fields)}, version = version + 1
            WHERE id = %s
            RETURNING id, name, description, status, service_type, version, created_at
        '''
        
        cursor.execute(update_query, tuple(params))
        tender = cursor.fetchone()
        
        if not tender:
            return jsonify({"reason": "Tender not found"}), 404

        conn.commit()

        return jsonify({
            "id": tender[0],
            "name": tender[1],
            "description": tender[2],
            "status": tender[3],
            "serviceType": tender[4],
            "version": tender[5],
            "createdAt": tender[6]
        }), 200

    except Exception as e:
        return jsonify({"reason": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

if __name__ == '__main__':
    (host, port) = os.getenv("SERVER_ADDRESS").split(":")
    create_tables()

    app.run(host, port, debug=True)