"""HTTP client liviano para la API de Contífico."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional

import requests


class ContificoClientError(RuntimeError):
    """Error base para problemas de comunicación con Contífico."""


class ContificoAPIError(ContificoClientError):
    """Errores retornados por la API de Contífico."""

    def __init__(self, status_code: int, detail: str, payload: Any | None = None) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.payload = payload


@dataclass(slots=True)
class ContificoCredentials:
    """Agrupa las credenciales necesarias para hablar con Contífico."""

    api_key: str
    api_token: str
    base_url: str = "https://api.contifico.com/sistema/api/v1"

    def headers(self) -> Dict[str, str]:
        return {
            "Authorization": self.api_key,
            "X-Api-Token": self.api_token,
            "Accept": "application/json",
            "Content-Type": "application/json; charset=UTF-8",
        }


class ContificoClient:
    """Cliente HTTP mínimo que cubre operaciones de catálogo e inventario."""

    def __init__(self, credentials: ContificoCredentials, *, timeout: float = 30.0) -> None:
        self.credentials = credentials
        self.base_url = credentials.base_url.rstrip("/")
        self.timeout = timeout

    def _request(
        self,
        method: str,
        endpoint: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
    ) -> Any:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        response = requests.request(
            method=method,
            url=url,
            headers=self.credentials.headers(),
            params=params,
            json=json_body,
            timeout=self.timeout,
        )
        payload = self._safe_json(response)
        if response.status_code >= 400:
            detail = self._extract_error_message(response, payload)
            raise ContificoAPIError(response.status_code, detail, payload=payload)
        return payload

    def list_products(self, *, page: int = 1, page_size: int = 100, search: str | None = None) -> Iterable[Dict[str, Any]]:
        """Devuelve productos paginados del catálogo de Contífico."""

        params: Dict[str, Any] = {
            "page": page,
            "page_size": page_size,
        }
        if search:
            params["search"] = search
        payload = self._request("GET", "producto/", params=params)
        if isinstance(payload, dict):
            results = payload.get("results")
            if isinstance(results, list):
                return results
        if isinstance(payload, list):
            return payload
        return []

    def get_product_by_sku(self, sku: str) -> Dict[str, Any] | None:
        """Obtiene un producto filtrando por SKU."""

        results = self.list_products(search=sku)
        for product in results:
            if isinstance(product, dict) and product.get("codigo_principal") == sku:
                return product
        return None

    def create_or_update_product(self, *, sku: str, name: str, price: float, tax: str | None = None, **extra: Any) -> Dict[str, Any]:
        """Crea o actualiza un producto simple.

        Contífico utiliza ``codigo_principal`` como identificador de producto.
        Este método ejecuta un POST idempotente usando el SKU como llave.
        """

        body: Dict[str, Any] = {
            "codigo_principal": sku,
            "nombre": name,
            "precio": price,
        }
        if tax:
            body["impuesto"] = tax
        body.update(extra)
        return self._request("POST", "producto/", json_body=body)

    def create_inventory_movement(
        self,
        *,
        warehouse_id: str,
        lines: list[dict[str, Any]],
        observation: str,
        endpoint: str = "inventario/guia/",
        document_type: str = "AJUSTE_RFID",
    ) -> Dict[str, Any]:
        """Registra un movimiento de inventario usando una guía de remisión.

        ``lines`` debe incluir ``codigo_principal`` y ``cantidad`` por cada SKU
        involucrado. Ajusta el ``endpoint`` si tu instancia usa rutas distintas
        (por ejemplo ``registro/documento/`` para ajustes). ``document_type`` se
        envía como observación para identificar el origen RFID.
        """

        body = {
            "bodega_origen": warehouse_id,
            "bodega_destino": warehouse_id,
            "observacion": f"{document_type}: {observation}",
            "detalle": lines,
        }
        return self._request("POST", endpoint, json_body=body)

    @staticmethod
    def _safe_json(response: requests.Response) -> Any | None:
        try:
            return response.json()
        except ValueError:
            return None

    @staticmethod
    def _extract_error_message(response: requests.Response, payload: Any | None) -> str:
        if isinstance(payload, dict):
            for key in ("mensaje", "message", "detail", "error"):
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        text = response.text.strip()
        if text:
            return text
        return f"Error {response.status_code} al comunicarse con Contífico"
