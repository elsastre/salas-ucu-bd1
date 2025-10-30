from fastapi import FastAPI, HTTPException
import os, mysql.connector

app = FastAPI(title="UCU Salas - BD1", version="0.1.0")

def get_conn():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASS", "root"),
        database=os.getenv("DB_NAME", "salas_db"),
        autocommit=True
    )

@app.get("/health")
def health():
    try:
        conn = get_conn()
        conn.close()
        return {"status": "ok", "db": "reachable"}
    except Exception as e:
        return {"status": "ok", "db": f"error: {e.__class__.__name__}"}

@app.get("/turnos")
def listar_turnos():
    try:
        conn = get_conn()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT id_turno, hora_inicio, hora_fin FROM turno ORDER BY id_turno;")
        rows = cur.fetchall()
        cur.close(); conn.close()
        return rows
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
