"""Local, append-only store of evaluations (stdlib sqlite3). The table design follows the platform
schema in docs/DATABASE.md so it can move to PostgreSQL later. Stored evaluations are never edited:
re-running an evaluation adds a new row, and old rows keep their algorithm and profile versions."""
from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS evaluations (
  id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  category TEXT NOT NULL,
  profile_id TEXT NOT NULL,
  profile_version TEXT NOT NULL,
  algorithm_version TEXT NOT NULL,
  input_hash TEXT NOT NULL,
  request_json TEXT NOT NULL,
  result_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS product_scores (
  evaluation_id TEXT NOT NULL REFERENCES evaluations(id),
  product_id TEXT NOT NULL,
  name TEXT NOT NULL,
  overall_score REAL,
  confidence REAL,
  coverage REAL,
  eligibility TEXT NOT NULL,
  PRIMARY KEY (evaluation_id, product_id)
);
CREATE INDEX IF NOT EXISTS idx_scores_name ON product_scores(name);
CREATE TRIGGER IF NOT EXISTS evaluations_immutable BEFORE UPDATE ON evaluations
BEGIN SELECT RAISE(ABORT, 'evaluations are immutable'); END;
"""


def connect(path) -> sqlite3.Connection:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path))
    con.executescript(SCHEMA)
    return con


def save(path, request: dict, result: dict) -> str:
    eid = str(uuid.uuid4())
    con = connect(path)
    try:
        with con:
            con.execute("INSERT INTO evaluations (id, category, profile_id, profile_version, algorithm_version, input_hash, "
                        "request_json, result_json) VALUES (?,?,?,?,?,?,?,?)",
                        (eid, result["category"], result["profile"], result["profile_version"], result["algorithm_version"],
                         result["input_hash"], json.dumps(request, sort_keys=True, default=str),
                         json.dumps(result, sort_keys=True, default=str)))
            for e in result["evaluations"]:
                con.execute("INSERT INTO product_scores VALUES (?,?,?,?,?,?,?)",
                            (eid, e["product_id"], e["name"], e["overall_score"], e["confidence"], e["coverage"], e["eligibility"]))
    finally:
        con.close()
    return eid


def load(path, eid: str) -> dict | None:
    con = connect(path)
    try:
        row = con.execute("SELECT request_json, result_json FROM evaluations WHERE id = ?", (eid,)).fetchone()
    finally:
        con.close()
    return {"request": json.loads(row[0]), "result": json.loads(row[1])} if row else None


def history(path, name: str | None = None) -> list:
    con = connect(path)
    try:
        q = ("SELECT e.id, e.created_at, e.category, s.name, s.overall_score, s.eligibility, e.algorithm_version "
             "FROM evaluations e JOIN product_scores s ON s.evaluation_id = e.id")
        args = ()
        if name:
            q += " WHERE s.name LIKE ?"
            args = (f"%{name}%",)
        return con.execute(q + " ORDER BY e.created_at DESC", args).fetchall()
    finally:
        con.close()
