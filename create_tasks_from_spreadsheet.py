from __future__ import annotations

"""
Importa tarefas do Excel e cria no Runrun.it (API v1.0), 1 por linha.
Compatível com ratelimit-reset no formato ISO-8601 com timezone, ex:
2026-01-07T14:48:00+00:00

Dependências:
  pip install pandas openpyxl requests

Uso:
  export RUNRUNIT_APP_KEY="..."
  export RUNRUNIT_USER_TOKEN="..."
  python create_tasks_from_spreadsheet.py "tarefas.xlsx" --sheet "Plan1"

Planilha (colunas padrão; ajuste em build_task_from_row se quiser):
  title (str)              obrigatório
  board_id (int)           obrigatório
  description (str)        opcional
  desired_date (date/str)  opcional (ex.: 2026-01-31) ou vazio
  project_id (int)         opcional (ou default)
  type_id (int)            opcional (ou default)
  assignee_id (str)        opcional (ex.: "joao-silva")
  custom_* (any)           opcional (ex: custom_1, custom_42)
                           Colunas de campos customizados. O script busca o tipo
                           de cada campo (texto, número, data, etc.) na API do
                           Runrun.it e formata o valor adequadamente.
"""

import argparse
import json
import os
import re
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

import pandas as pd
import requests

API_URL = "https://runrun.it/api/v1.0"


# --- Helper Functions for Data Conversion ---


def _to_int(v: Any, default: Optional[int] = None) -> Optional[int]:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return default
    try:
        return int(v)
    except (ValueError, TypeError):
        return default


def _to_float(v: Any, default: Optional[float] = None) -> Optional[float]:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return default
    try:
        return float(v)
    except (ValueError, TypeError):
        return default


def _to_str(v: Any, default: Optional[str] = None) -> Optional[str]:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return default
    s = str(v)
    return s if s.strip() else default


def _to_desired_date(v: Any) -> Optional[str]:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, pd.Timestamp):
        dt = v.to_pydatetime()
        if dt.time() == datetime.min.time():
            return dt.date().isoformat()
        return dt.astimezone(timezone.utc).isoformat()
    if isinstance(v, datetime):
        if v.time() == datetime.min.time():
            return v.date().isoformat()
        return v.astimezone(timezone.utc).isoformat()
    s = str(v).strip()
    return s or None


# --- Custom Field Formatting Logic ---


def _format_custom_field(value: Any, field_def: dict[str, Any]) -> Any:
    """
    Formats a custom field value based on its type definition.
    """
    field_type = field_def.get("field_type")
    field_id = field_def.get("id")
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None

    # Simple types
    if field_type in ("text_short", "text_long", "email", "short_text", "numeric"):
        return str(value)
    if field_type == "number_integer":
        return _to_int(value)
    if field_type == "number_decimal":
        return _to_float(value)
    if field_type == "date":
        return _to_desired_date(value)

    # Complex types with strict validation
    if field_type in ("single_option", "multiple_options"):
        options = field_def.get("options", [])
        if not options:
            print(f"[WARN] Campo de seleção '{field_id}' não tem opções configuradas. Ignorando.")
            return None

        # Split by comma or semicolon
        values_to_find = [v.strip() for v in re.split("[,;]", str(value)) if v.strip()]
        available_labels = [str(o.get("label")) for o in options]

        found_options_data = []
        for val_to_find in values_to_find:
            found_id = None
            for option in options:
                if str(option.get("id")) == val_to_find or str(
                    option.get("label", "")
                ).lower() == val_to_find.lower():
                    found_id = option.get("id")
                    break

            if found_id is not None:
                found_options_data.append({"id": found_id})
            else:
                raise ValueError(
                    f"Valor '{val_to_find}' para o campo '{field_id}' não é uma opção válida. "
                    f"Opções disponíveis: {available_labels}"
                )

        if not found_options_data:
            return None

        return found_options_data[0] if field_type == "single_option" else found_options_data

    return value


# --- Main Task Building Function ---


def build_task_from_row(
    row: pd.Series,
    defaults: dict[str, Any],
    custom_field_defs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    # Standard fields
    title = _to_str(row.get("title"))
    board_id = _to_int(row.get("board_id"))
    description = _to_str(row.get("description"), defaults.get("description"))
    desired_date = _to_desired_date(row.get("desired_date"))
    assignee_id = _to_str(row.get("assignee_id"))
    type_id = _to_int(row.get("type_id"), defaults.get("type_id"))
    project_id = _to_int(row.get("project_id"), defaults.get("project_id"))

    # Validation for required fields
    missing = []
    if not title:
        missing.append("title")
    if not board_id:
        missing.append("board_id")
    if missing:
        raise ValueError(f"Colunas obrigatórias ausentes/vazias: {missing}")

    # Base task object
    task_obj: dict[str, Any] = {
        "board_id": board_id,
        "type_id": type_id,
        "project_id": project_id,
        "title": title,
        "description": description,
        "desired_date": desired_date,
    }

    if assignee_id:
        task_obj["assignments"] = [{"assignee_id": assignee_id}]

    # Custom fields processing
    custom_fields_payload = {}
    for col_name, value in row.items():
        if not isinstance(col_name, str) or not col_name.startswith("custom_") or pd.isna(value):
            continue

        field_def = custom_field_defs.get(col_name)
        if not field_def:
            continue

        formatted_value = _format_custom_field(value, field_def)
        if formatted_value is not None:
            custom_fields_payload[col_name] = formatted_value

    if custom_fields_payload:
        task_obj["custom_fields"] = custom_fields_payload

    return {k: v for k, v in task_obj.items() if v is not None}


# --- API Client ---


@dataclass
class RunrunClient:
    app_key: str
    user_token: str
    max_per_minute: int = 100
    window_seconds: int = 60
    session: requests.Session = field(default_factory=requests.Session, init=False)
    _timestamps: deque = field(default_factory=deque, init=False)

    def _throttle(self):
        while True:
            now = time.monotonic()
            while self._timestamps and (now - self._timestamps[0]) >= self.window_seconds:
                self._timestamps.popleft()
            if len(self._timestamps) < self.max_per_minute:
                return
            wait = self.window_seconds - (now - self._timestamps[0])
            time.sleep(wait if wait > 0 else 0.01)

    @staticmethod
    def _parse_ratelimit_reset_iso(value: str) -> float:
        v = (value or "").strip()
        if not v:
            raise ValueError("ratelimit-reset vazio")
        if v.endswith("Z"):
            v = v[:-1] + "+00:00"
        dt = datetime.fromisoformat(v)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).timestamp()

    def _request(self, method: str, endpoint: str, payload: Optional[dict] = None) -> Any:
        headers = {
            "App-Key": self.app_key,
            "User-Token": self.user_token,
            "Content-Type": "application/json",
        }
        url = f"{API_URL}/{endpoint}"
        for _ in range(8):
            self._throttle()
            resp = self.session.request(
                method, url, headers=headers, data=json.dumps(payload) if payload else None
            )
            self._timestamps.append(time.monotonic())
            if 200 <= resp.status_code < 300:
                return resp.json() if resp.content else {"ok": True}
            if resp.status_code == 429:
                reset_raw = resp.headers.get("ratelimit-reset") or resp.headers.get(
                    "RateLimit-Reset"
                )
                reset_ts = self._parse_ratelimit_reset_iso(reset_raw)
                wait = max(0.0, reset_ts - datetime.now(timezone.utc).timestamp()) + 0.25
                time.sleep(wait)
                continue
            raise RuntimeError(
                f"Erro na API (HTTP {resp.status_code}) em {method} {endpoint}. Response: {resp.text[:1000]}"
            )
        raise RuntimeError("Falha após múltiplas tentativas (429 persistente).")

    def create_task(self, task_obj: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "tasks", payload={"task": task_obj})

    def get_board_custom_fields(self, board_id: int) -> list[dict[str, Any]]:
        return self._request("GET", f"boards/{board_id}/fields?category=custom")

    def get_field_options(self, field_id: str) -> list[dict[str, Any]]:
        return self._request("GET", f"fields/{field_id}/options")


# --- Main Execution ---


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("xlsx_path", help="Caminho do .xlsx")
    ap.add_argument("--sheet", default=0, help="Nome ou ?ndice da aba (default: 0)")
    ap.add_argument("--dry-run", action="store_true", help="N?o chama API; s? imprime payloads")
    ap.add_argument("--max-per-minute", type=int, default=100, help="default: 100")
    args = ap.parse_args()

    app_key = os.environ.get("RUNRUNIT_APP_KEY", "").strip()
    user_token = os.environ.get("RUNRUNIT_USER_TOKEN", "").strip()
    if not args.dry_run and (not app_key or not user_token):
        raise SystemExit("Defina RUNRUNIT_APP_KEY e RUNRUNIT_USER_TOKEN no ambiente.")

    df = pd.read_excel(args.xlsx_path, sheet_name=args.sheet)
    defaults: dict[str, Any] = {"description": None}
    client = RunrunClient(
        app_key=app_key, user_token=user_token, max_per_minute=args.max_per_minute
    )

    board_fields_cache: dict[int, dict[str, Any]] = {}
    ok = 0
    fail = 0

    for i, row in df.iterrows():
        excel_row = i + 2
        try:
            board_id = _to_int(row.get("board_id"))
            if not board_id:
                raise ValueError("board_id ausente ou inválido.")

            # Fetch and cache custom field definitions if not already cached
            if board_id not in board_fields_cache:
                print(f"[INFO] Buscando definições de campos para o board_id={board_id}...")
                fields_list = []
                if not args.dry_run:
                    fields_list = client.get_board_custom_fields(board_id)

                processed_fields = {}
                for field_def in fields_list:
                    field_id = field_def.get("id")
                    if not field_id:
                        continue

                    if field_def.get("field_type") in ("single_option", "multiple_options"):
                        print(f"[INFO] ...buscando opções para o campo {field_id}...")
                        field_def["options"] = []
                        if not args.dry_run:
                            field_def["options"] = client.get_field_options(field_id)

                    processed_fields[field_id] = field_def

                board_fields_cache[board_id] = processed_fields
                print(f"[INFO] Definições para board_id={board_id} cacheadas.")

            custom_field_defs = board_fields_cache[board_id]
            task_obj = build_task_from_row(row, defaults, custom_field_defs)

            if args.dry_run:
                print(
                    json.dumps(
                        {"row": excel_row, "payload": {"task": task_obj}},
                        ensure_ascii=False,
                        indent=2,
                    )
                )
            else:
                resp = client.create_task(task_obj)
                task_id = resp.get("id") or resp.get("task", {}).get("id")
                print(f"[OK] row={excel_row} task_id={task_id}")
            ok += 1

        except Exception as e:
            fail += 1
            print(f"[FAIL] row={excel_row} error={e}")

    print(f"\nDone: OK={ok} FAIL={fail}")


if __name__ == "__main__":
    main()