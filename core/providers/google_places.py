"""Places API (New), Text Search only. No retries, redirects or enrichment."""
import http.client
import json
import math
import os

from .models import LeadCandidate
from .search_query import normalize_neighborhood
from core.lead_filter import possui_site
from core.prospecting.limits import DEFAULT_MAX_REQUESTS

ENDPOINT = "https://places.googleapis.com/v1/places:searchText"
FIELD_MASK = ",".join((
    "places.id", "places.displayName", "places.formattedAddress", "places.nationalPhoneNumber",
    "places.websiteUri", "places.rating", "places.userRatingCount", "places.googleMapsLinks.placeUri",
    "places.location", "nextPageToken",
))


class GooglePlacesError(RuntimeError):
    pass


class GooglePlacesSafetyLimitError(GooglePlacesError):
    pass


class GooglePlacesConfigurationError(GooglePlacesError):
    pass


class GooglePlacesHTTPError(GooglePlacesError):
    def __init__(self, status, *, api_status=None, api_message=None):
        self.status = status
        self.api_status = api_status
        self.api_message = api_message
        super().__init__(f"Google Places HTTP error: {status}")


class GooglePlacesResponseError(GooglePlacesError):
    pass


class GooglePlacesTransportError(GooglePlacesError):
    pass


def build_query(city: str, segment: str, neighborhood: str | None = None) -> str:
    if not isinstance(city, str) or not city.strip() or not isinstance(segment, str) or not segment.strip():
        raise ValueError("city and segment must be nonempty text")
    neighborhood = normalize_neighborhood(neighborhood)
    location = f"{neighborhood}, {city.strip()}" if neighborhood else city.strip()
    return f"{segment.strip()} em {location}"


def _http_400_diagnostic(raw, key):
    """Allow only two bounded, single-line fields; never retain the raw body."""
    try:
        data = json.loads(raw)
    except (ValueError, TypeError, UnicodeError):
        return {}
    error = data.get("error") if isinstance(data, dict) else None
    if not isinstance(error, dict):
        return {}
    diagnostic = {}
    for field in ("status", "message"):
        value = error.get(field)
        if isinstance(value, str):
            value = value.replace(key, "[REDACTED]")
            value = " ".join("".join(c if c.isprintable() else " " for c in value).split())
            diagnostic[f"api_{field}"] = value[:500]
    return diagnostic


def _post(payload, headers, timeout):
    connection = http.client.HTTPSConnection("places.googleapis.com", timeout=timeout)
    try:
        connection.request("POST", "/v1/places:searchText", body=json.dumps(payload, ensure_ascii=False).encode("utf-8"), headers=headers)
        response = connection.getresponse()
        return response.status, response.read()
    finally:
        connection.close()


def normalize_place(place, *, city, segment):
    if not isinstance(place, dict):
        raise GooglePlacesResponseError("Unexpected place structure")
    def text(key, container=place):
        value = container.get(key)
        if value is not None and not isinstance(value, str):
            raise GooglePlacesResponseError("Unexpected text field type")
        return value or None
    def number(key, container=place, integer=False):
        value = container.get(key)
        if value is not None and (type(value) not in (int, float) or not math.isfinite(value)
                                  or (integer and type(value) is not int)):
            raise GooglePlacesResponseError("Unexpected numeric field type")
        return value
    name = place.get("displayName", {})
    location = place.get("location", {})
    maps_links = place.get("googleMapsLinks", {})
    if not isinstance(name, dict) or not isinstance(location, dict) or not isinstance(maps_links, dict):
        raise GooglePlacesResponseError("Unexpected nested place structure")
    website = text("websiteUri")
    website = website.strip() if possui_site({"site": website}) else None
    return LeadCandidate(
        provider="google_places", provider_place_id=text("id"), empresa=text("text", name),
        cidade=city, segmento=segment, telefone=text("nationalPhoneNumber"),
        site=website, endereco=text("formattedAddress"), avaliacao=number("rating"),
        quantidade_avaliacoes=number("userRatingCount", integer=True), google_maps=text("placeUri", maps_links),
        latitude=number("latitude", location), longitude=number("longitude", location),
    )


class GooglePlacesProvider:
    """Sequential pages with explicit budget; request_count resets per search.

    transport(payload, headers, timeout) -> (HTTP status, JSON bytes) is injectable.
    API keys are read only from the environment; raw transport errors/responses
    never become public error text. Instances are not intended for concurrent use.
    """
    def __init__(self, *, timeout=30, max_requests=DEFAULT_MAX_REQUESTS, transport=None, log=None):
        key = os.environ.get("GOOGLE_PLACES_API_KEY", "").strip()
        if not key:
            raise GooglePlacesConfigurationError("Set GOOGLE_PLACES_API_KEY before searching")
        if not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be positive and finite")
        if type(max_requests) is not int or max_requests < 1:
            raise ValueError("max_requests must be a positive integer")
        self._key = key
        self.timeout = timeout
        self.max_requests = max_requests
        self._transport = transport or _post
        self._log = log
        self.request_count = 0
        self.pages_fetched = 0

    def _emit(self, message):
        if self._log:
            self._log(message.replace(self._key, "[REDACTED]"))

    def search(self, *, city, segment, max_results=50, neighborhood=None):
        return list(self.iter_search(city=city, segment=segment, max_results=max_results, neighborhood=neighborhood))

    def iter_search(self, *, city, segment, max_results=50, should_stop=lambda: False, neighborhood=None):
        """Same pagination, consumed lazily; None uses the existing request budget.

        Callers can stop after enough accepted leads without another HTTP call.
        Cancellation is checked before requests and between candidates.
        """
        self.request_count = 0
        self.pages_fetched = 0
        query = build_query(city, segment, neighborhood)
        if max_results is not None and (type(max_results) is not int or max_results < 0):
            raise ValueError("max_results must be a nonnegative integer")
        if max_results == 0:
            return
        received, tokens = 0, set()
        token = None
        self._emit("Google Places: search started")
        while max_results is None or received < max_results:
            if should_stop():
                return
            if self.request_count >= self.max_requests:
                raise GooglePlacesSafetyLimitError("Google Places request budget exhausted")
            payload = {"textQuery": query, "languageCode": "pt-BR", "pageSize": 20 if max_results is None else min(20, max_results - received)}
            if token:
                payload["pageToken"] = token
            headers = {"Content-Type": "application/json", "X-Goog-Api-Key": self._key, "X-Goog-FieldMask": FIELD_MASK}
            self.request_count += 1
            try:
                status, raw = self._transport(payload, headers, self.timeout)
            except TimeoutError:
                raise GooglePlacesTransportError("Google Places request timed out") from None
            except Exception:
                raise GooglePlacesTransportError("Google Places connection failed") from None
            if type(status) is not int:
                raise GooglePlacesResponseError("Invalid HTTP status")
            if not 200 <= status < 300:
                diagnostic = _http_400_diagnostic(raw, self._key) if status == 400 else {}
                raise GooglePlacesHTTPError(status, **diagnostic)
            try:
                data = json.loads(raw)
            except (ValueError, TypeError, UnicodeError):
                raise GooglePlacesResponseError("Invalid Google Places JSON") from None
            if not isinstance(data, dict):
                raise GooglePlacesResponseError("Unexpected response structure")
            if "error" in data:
                raise GooglePlacesResponseError("Google Places API returned an error")
            places = data.get("places", [])
            next_token = data.get("nextPageToken")
            if not isinstance(places, list) or (next_token is not None and not isinstance(next_token, str)):
                raise GooglePlacesResponseError("Unexpected places or pagination structure")
            candidates = [normalize_place(place, city=city, segment=segment) for place in places]
            self.pages_fetched += 1
            self._emit(f"Google Places: page {self.request_count}, {len(candidates)} results")
            for candidate in candidates:
                if should_stop():
                    return
                if max_results is not None and received >= max_results:
                    break
                received += 1
                yield candidate
            if (max_results is not None and received >= max_results) or not next_token:
                break
            if next_token in tokens:
                raise GooglePlacesResponseError("Repeated pagination token")
            tokens.add(next_token)
            token = next_token
        self._emit(f"Google Places: completed, {received} results, {self.request_count} requests")
