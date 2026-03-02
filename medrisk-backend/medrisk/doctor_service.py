from __future__ import annotations

import math
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx

GOOGLE_PLACES_API_KEY = (
    os.getenv("GOOGLE_PLACES_API_KEY")
    or os.getenv("GOOGLE_MAPS_API_KEY")
    or os.getenv("GOOGLE_API_KEY")
)

GOOGLE_PLACES_TEXT_ENDPOINT = "https://places.googleapis.com/v1/places:searchText"

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.nchc.org.tw/api/interpreter",
]

CACHE_TTL_S = int(os.getenv("MEDRISK_DOCTOR_CACHE_TTL_S", "900"))  # 15 min
MAX_RADIUS_KM = 25.0

# Try multiple types because in many cities doctors are tagged as clinics/hospitals.
GOOGLE_INCLUDED_TYPES = [
    "doctor",
    "medical_clinic",
    "medical_center",
    "hospital",
    "general_hospital",
]

SPECIALTY_QUERY_MAP: Dict[str, str] = {
    "General Physician": "doctor",
    "Cardiologist": "cardiologist",
    "Endocrinologist": "endocrinologist",
    "Nephrologist": "nephrologist",
    "Gastroenterologist": "gastroenterologist",
    "Hematologist": "hematologist",
    "Pulmonologist": "pulmonologist",
    "Dermatologist": "dermatologist",
    "Gynecologist": "gynecologist",
    "ENT Specialist": "ENT specialist",
    "Diabetologist": "diabetologist",
}

SPECIALTY_KEYWORDS: Dict[str, List[str]] = {
    "Cardiologist": ["cardio", "heart"],
    "Endocrinologist": ["endocr", "thyroid", "hormone", "diabet"],
    "Nephrologist": ["nephro", "kidney", "renal"],
    "Gastroenterologist": ["gastro", "liver", "hepat", "digest"],
    "Hematologist": ["hemat", "blood"],
    "Pulmonologist": ["pulmo", "chest", "lung", "respir"],
    "Dermatologist": ["derma", "skin"],
    "Gynecologist": ["gyn", "obstet", "women"],
    "ENT Specialist": ["ent", "ear", "nose", "throat"],
    "Diabetologist": ["diabet", "endocr"],
}

_cache: Dict[Tuple[int, int, str, int, int], Tuple[float, List[Dict[str, Any]], Dict[str, Any]]] = {}


def _cache_key(lat: float, lng: float, specialty: str, radius_km: float, limit: int) -> Tuple[int, int, str, int, int]:
    return (int(lat * 1000), int(lng * 1000), specialty or "", int(radius_km * 10), int(limit))


def _cache_get(key):
    item = _cache.get(key)
    if not item:
        return None
    ts, doctors, meta = item
    if time.time() - ts > CACHE_TTL_S:
        _cache.pop(key, None)
        return None
    m = dict(meta)
    m["cacheHit"] = True
    return doctors, m


def _cache_set(key, doctors, meta):
    m = dict(meta)
    m["cacheHit"] = False
    _cache[key] = (time.time(), doctors, m)


def _norm_specialty(s: Optional[str]) -> str:
    s = (s or "").strip()
    return s or "General Physician"


def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dl / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


def _google_field_mask() -> str:
    # FieldMask is required for Places Text Search (New). :contentReference[oaicite:0]{index=0}
    return ",".join(
        [
            "places.id",
            "places.displayName",
            "places.formattedAddress",
            "places.location",
            "places.rating",
            "places.userRatingCount",
            "places.websiteUri",
            "places.googleMapsUri",
            "nextPageToken",
        ]
    )


def _google_text_query(specialty: str) -> str:
    base = SPECIALTY_QUERY_MAP.get(specialty, specialty)
    # Keep query short & categorical to avoid INVALID_ARGUMENT in some configs.
    if specialty == "General Physician":
        return "doctor clinic"
    return f"{base} doctor"


def _maps_search_url(lat: float, lng: float, q: Optional[str] = None) -> str:
    query = f"{lat},{lng}" if not q else f"{q} {lat},{lng}"
    return f"https://www.google.com/maps/search/?api=1&query={query}"


def _matches_specialty(name: str, tags: Dict[str, Any], specialty: str) -> bool:
    if specialty == "General Physician":
        return True
    kws = SPECIALTY_KEYWORDS.get(specialty, [])
    if not kws:
        return True
    hay = " ".join(
        [
            name.lower(),
            str(tags.get("healthcare:speciality") or "").lower(),
            str(tags.get("speciality") or "").lower(),
            str(tags.get("description") or "").lower(),
            str(tags.get("healthcare") or "").lower(),
            str(tags.get("amenity") or "").lower(),
        ]
    )
    return any(kw in hay for kw in kws)


def _build_address(tags: Dict[str, Any]) -> str:
    full = str(tags.get("addr:full") or "").strip()
    if full:
        return full
    parts = [
        tags.get("addr:housenumber"),
        tags.get("addr:street"),
        tags.get("addr:suburb"),
        tags.get("addr:city"),
        tags.get("addr:state"),
        tags.get("addr:postcode"),
    ]
    parts = [str(p).strip() for p in parts if p]
    return ", ".join(parts) if parts else "Address not available"


def _guess_name(tags: Dict[str, Any]) -> str:
    name = str(tags.get("name") or tags.get("operator") or "").strip()
    if name:
        return name
    # synthesize a useful label instead of empty/“Doctor/Clinic”
    hc = str(tags.get("healthcare") or "").strip()
    am = str(tags.get("amenity") or "").strip()
    if "hospital" in (hc + am):
        return "Hospital"
    if "clinic" in (hc + am) or "medical" in (hc + am):
        return "Medical Clinic"
    if "doctors" in (hc + am) or "doctor" in (hc + am):
        return "Doctor"
    return "Clinic"


def _get_url(tags: Dict[str, Any]) -> Optional[str]:
    for k in ("website", "contact:website", "url", "contact:url"):
        v = str(tags.get(k) or "").strip()
        if v.startswith("http://") or v.startswith("https://"):
            return v
    return None


async def _google_places_search(
    *, lat: float, lng: float, specialty: str, radius_km: float, limit: int
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    meta: Dict[str, Any] = {"provider": "google", "googleEnabled": bool(GOOGLE_PLACES_API_KEY)}
    if not GOOGLE_PLACES_API_KEY:
        meta["googleError"] = "GOOGLE_PLACES_API_KEY not set"
        return [], meta

    radius_m = float(max(1000.0, min(radius_km, MAX_RADIUS_KM) * 1000.0))
    text_query = _google_text_query(specialty)

    out: List[Dict[str, Any]] = []
    seen_ids = set()

    async with httpx.AsyncClient(timeout=httpx.Timeout(12.0, connect=6.0)) as client:
        errors: List[str] = []

        # Try multiple includedType values to increase recall. :contentReference[oaicite:1]{index=1}
        for included_type in GOOGLE_INCLUDED_TYPES:
            if len(out) >= limit:
                break

            page_token: Optional[str] = None
            for _page in range(3):  # up to 60 results total (3*20)
                body: Dict[str, Any] = {
                    "textQuery": text_query,
                    "languageCode": "en",
                    "regionCode": "IN",
                    "pageSize": 20,
                    "rankPreference": "DISTANCE",  # allowed enum :contentReference[oaicite:2]{index=2}
                    "includedType": included_type,
                    "locationBias": {
                        "circle": {"center": {"latitude": float(lat), "longitude": float(lng)}, "radius": radius_m}
                    },
                }
                if page_token:
                    body["pageToken"] = page_token

                resp = await client.post(
                    GOOGLE_PLACES_TEXT_ENDPOINT,
                    json=body,
                    headers={
                        "Content-Type": "application/json",
                        "X-Goog-Api-Key": GOOGLE_PLACES_API_KEY,
                        "X-Goog-FieldMask": _google_field_mask(),
                    },
                )

                if resp.status_code >= 400:
                    # Save the real error so you can fix config instantly.
                    errors.append(f"{included_type}: HTTP {resp.status_code} - {resp.text[:300]}")
                    break

                data = resp.json() or {}
                places = data.get("places") or []
                for p in places:
                    pid = str(p.get("id") or "")
                    display = (p.get("displayName") or {}).get("text") or ""
                    addr = p.get("formattedAddress") or ""
                    loc = p.get("location") or {}
                    plat = float(loc.get("latitude") or 0.0)
                    plng = float(loc.get("longitude") or 0.0)
                    if not pid or pid in seen_ids or not display or not plat or not plng:
                        continue

                    seen_ids.add(pid)
                    dist_m = _haversine_m(lat, lng, plat, plng)

                    out.append(
                        {
                            "id": pid,
                            "name": display,
                            "specialty": specialty,
                            "address": addr or "Address not available",
                            "location": {"lat": plat, "lng": plng},
                            "rating": p.get("rating"),
                            "userRatingsTotal": p.get("userRatingCount"),
                            "website": p.get("websiteUri"),
                            "mapsUrl": p.get("googleMapsUri") or _maps_search_url(plat, plng, display),
                            "bookingUrl": p.get("websiteUri") or p.get("googleMapsUri"),
                            "distanceMeters": dist_m,
                            "distanceKm": dist_m / 1000.0,
                        }
                    )

                    if len(out) >= limit:
                        break

                page_token = data.get("nextPageToken")
                if not page_token or len(out) >= limit:
                    break

                await time.sleep(0.2)

        out.sort(key=lambda x: x.get("distanceMeters", 9e18))
        meta["count"] = len(out)
        if errors and not out:
            meta["googleError"] = errors[0]
            meta["googleErrorsSample"] = errors[:3]
        return out[:limit], meta


async def _overpass_search(
    *, lat: float, lng: float, specialty: str, radius_km: float, limit: int
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    meta: Dict[str, Any] = {"provider": "osm_overpass"}
    radius_m = int(max(2000.0, min(radius_km, MAX_RADIUS_KM) * 1000.0))

    # Wider net than before (clinic/medical_center/doctor/hospital).
    query = f"""
[out:json][timeout:18];
(
  nwr(around:{radius_m},{lat},{lng})["amenity"~"hospital|clinic|doctors"];
  nwr(around:{radius_m},{lat},{lng})["healthcare"~"hospital|clinic|doctor|centre|center|medical_centre|medical_center"];
);
out center {min(max(limit * 6, 120), 350)};
""".strip()

    last_err: Optional[str] = None

    async with httpx.AsyncClient(timeout=httpx.Timeout(14.0, connect=6.0)) as client:
        for ep in OVERPASS_ENDPOINTS:
            try:
                resp = await client.post(ep, data=query, headers={"Content-Type": "text/plain"})
                if resp.status_code == 429:
                    last_err = f"{ep} -> 429 Too Many Requests"
                    continue
                if resp.status_code >= 400:
                    last_err = f"{ep} -> HTTP {resp.status_code}"
                    continue

                data = resp.json() or {}
                elements = data.get("elements") or []
                if not isinstance(elements, list) or not elements:
                    meta["count"] = 0
                    return [], meta

                all_places: List[Dict[str, Any]] = []
                for el in elements:
                    tags = el.get("tags") if isinstance(el.get("tags"), dict) else {}

                    plat = el.get("lat")
                    plng = el.get("lon")
                    if plat is None or plng is None:
                        center = el.get("center") if isinstance(el.get("center"), dict) else None
                        if center:
                            plat = center.get("lat")
                            plng = center.get("lon")

                    try:
                        plat_f = float(plat)
                        plng_f = float(plng)
                    except Exception:
                        continue

                    name = _guess_name(tags)
                    dist_m = _haversine_m(lat, lng, plat_f, plng_f)
                    website = _get_url(tags)

                    all_places.append(
                        {
                            "id": f"osm:{el.get('type')}:{el.get('id')}",
                            "name": name,
                            "specialty": specialty,
                            "address": _build_address(tags),
                            "location": {"lat": plat_f, "lng": plng_f},
                            "rating": None,
                            "userRatingsTotal": None,
                            "website": website,
                            "mapsUrl": _maps_search_url(plat_f, plng_f, q=name),
                            "bookingUrl": website or _maps_search_url(plat_f, plng_f, q=name),
                            "distanceMeters": dist_m,
                            "distanceKm": dist_m / 1000.0,
                            "_tags": tags,
                        }
                    )

                # Dedup
                uniq: Dict[Tuple[str, int, int], Dict[str, Any]] = {}
                for d in all_places:
                    key = (d["name"].lower(), int(d["location"]["lat"] * 10000), int(d["location"]["lng"] * 10000))
                    if key not in uniq or d["distanceMeters"] < uniq[key]["distanceMeters"]:
                        uniq[key] = d

                all_places = list(uniq.values())
                all_places.sort(key=lambda x: x.get("distanceMeters", 9e18))

                # Specialty filter (best-effort); relax if it would hide everything.
                if specialty != "General Physician":
                    filtered = [d for d in all_places if _matches_specialty(d["name"], d.get("_tags", {}), specialty)]
                    if filtered:
                        for d in filtered:
                            d.pop("_tags", None)
                        meta["count"] = len(filtered)
                        meta["specialtyRelaxed"] = False
                        return filtered[:limit], meta
                    meta["specialtyRelaxed"] = True

                for d in all_places:
                    d.pop("_tags", None)
                meta["count"] = len(all_places)
                return all_places[:limit], meta

            except Exception as e:
                last_err = f"{ep} -> {type(e).__name__}: {e}"
                continue

    meta["overpassError"] = last_err or "Overpass failed"
    meta["count"] = 0
    return [], meta


async def search_nearby_doctors(
    *,
    lat: float,
    lng: float,
    specialty: Optional[str] = None,
    radius_km: float = 12.0,
    limit: int = 30,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    specialty_norm = _norm_specialty(specialty)
    radius_km = float(max(2.0, min(radius_km, MAX_RADIUS_KM)))
    limit = int(max(1, min(limit, 60)))

    key = _cache_key(lat, lng, specialty_norm, radius_km, limit)
    cached = _cache_get(key)
    if cached:
        return cached

    # 1) Google (best)
    doctors, meta_g = await _google_places_search(
        lat=lat, lng=lng, specialty=specialty_norm, radius_km=radius_km, limit=limit
    )
    if doctors:
        meta = {"providerUsed": "google", "google": meta_g}
        _cache_set(key, doctors, meta)
        return doctors, meta

    # 2) Overpass fallback: if few results, auto-expand radius once.
    doctors1, meta_o1 = await _overpass_search(
        lat=lat, lng=lng, specialty=specialty_norm, radius_km=radius_km, limit=limit
    )
    if len(doctors1) >= min(8, limit):
        meta = {"providerUsed": "osm_overpass", "google": meta_g, "osm": meta_o1}
        _cache_set(key, doctors1, meta)
        return doctors1, meta

    # expand radius to max for city-like searches
    doctors2, meta_o2 = await _overpass_search(
        lat=lat, lng=lng, specialty=specialty_norm, radius_km=MAX_RADIUS_KM, limit=limit
    )
    doctors = doctors2 if len(doctors2) > len(doctors1) else doctors1
    meta = {"providerUsed": "osm_overpass", "google": meta_g, "osm": (meta_o2 if doctors is doctors2 else meta_o1)}
    _cache_set(key, doctors, meta)
    return doctors, meta