"""Sincronización básica de eventos RFID hacia Contífico."""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv

from .contifico_client import ContificoClient, ContificoCredentials

load_dotenv()


def load_events(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("El archivo de eventos debe contener una lista JSON")
    normalized: list[dict[str, Any]] = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        epc = str(entry.get("epc", "")).strip()
        sku = str(entry.get("sku", "")).strip()
        if not epc or not sku:
            continue
        normalized.append({
            "epc": epc,
            "sku": sku,
            "timestamp": entry.get("timestamp"),
            "bodega": entry.get("bodega"),
        })
    return normalized


def aggregate_by_sku(events: list[dict[str, Any]]) -> Counter[str]:
    counter: Counter[str] = Counter()
    for event in events:
        sku = event["sku"]
        counter[sku] += 1
    return counter


def build_payload_lines(aggregated: Counter[str]) -> list[Dict[str, Any]]:
    lines: list[Dict[str, Any]] = []
    for sku, quantity in aggregated.items():
        lines.append({
            "codigo_principal": sku,
            "cantidad": quantity,
        })
    return lines


def run_sync(args: argparse.Namespace) -> None:
    credentials = ContificoCredentials(
        api_key=args.api_key,
        api_token=args.api_token,
        base_url=args.base_url,
    )
    client = ContificoClient(credentials)

    events = load_events(Path(args.events))
    aggregated = aggregate_by_sku(events)
    lines = build_payload_lines(aggregated)

    if args.dry_run:
        print("--- RESUMEN RFID (DRY-RUN) ---")
        for sku, quantity in aggregated.items():
            print(f"SKU={sku} cantidad={quantity}")
        print("Payload sugerido:")
        payload = {
            "bodega_origen": args.warehouse_id,
            "bodega_destino": args.warehouse_id,
            "detalle": lines,
            "observacion": f"{args.document_type}: {args.observation}",
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    response = client.create_inventory_movement(
        warehouse_id=args.warehouse_id,
        lines=lines,
        observation=args.observation,
        endpoint=args.endpoint,
        document_type=args.document_type,
    )
    print("Movimiento registrado en Contífico:")
    print(json.dumps(response, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    default_api_key = os.getenv("CONTIFICO_API_KEY")
    default_api_token = os.getenv("CONTIFICO_API_TOKEN")
    default_base_url = os.getenv("CONTIFICO_BASE_URL", "https://api.contifico.com/sistema/api/v1")
    default_endpoint = os.getenv("CONTIFICO_MOVEMENT_ENDPOINT", "inventario/guia/")
    default_document_type = os.getenv("CONTIFICO_DOCUMENT_TYPE", "AJUSTE_RFID")

    parser = argparse.ArgumentParser(description="Sincroniza lecturas RFID hacia Contífico")
    parser.add_argument("--events", required=True, help="Ruta al archivo JSON con eventos RFID (lista de diccionarios)")
    parser.add_argument("--warehouse-id", required=True, help="Bodega origen/destino para el movimiento")
    parser.add_argument(
        "--api-key",
        default=default_api_key,
        required=default_api_key is None,
        help="Authorization provisto por Contífico (o usa CONTIFICO_API_KEY)",
    )
    parser.add_argument(
        "--api-token",
        default=default_api_token,
        required=default_api_token is None,
        help="X-Api-Token provisto por Contífico (o usa CONTIFICO_API_TOKEN)",
    )
    parser.add_argument(
        "--base-url",
        default=default_base_url,
        help="URL base de la API de Contífico (o usa CONTIFICO_BASE_URL)",
    )
    parser.add_argument(
        "--endpoint",
        default=default_endpoint,
        help="Endpoint para registrar el movimiento de inventario (o usa CONTIFICO_MOVEMENT_ENDPOINT)",
    )
    parser.add_argument("--observation", default="Ajuste automático RFID", help="Observación del movimiento")
    parser.add_argument(
        "--document-type",
        default=default_document_type,
        help="Etiqueta de documento que se incluirá en la observación (o usa CONTIFICO_DOCUMENT_TYPE)",
    )
    parser.add_argument("--dry-run", action="store_true", help="No envía nada a Contífico, solo muestra el payload")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    run_sync(args)


if __name__ == "__main__":
    main()
