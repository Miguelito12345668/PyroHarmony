from pydantic import BaseModel


class ZoneInfo(BaseModel):
    id: str
    display_name: str
    bbox: list[float]
    enabled: bool


class ZonesResponse(BaseModel):
    zones: list[ZoneInfo]


class CalendarResponse(BaseModel):
    zone: str
    display_name: str
    years: list[int]
    months: list[int]
    matrix: list[list[int]]
    matrix_modis: list[list[int]]
    matrix_viirs: list[list[int]]
    first_viirs_year: int | None = None
    median_by_month: list[float]
    current_year: int
    current_month: int
    current_count: int
    median_for_current_month: float
    current_anomaly_pct: float
    total_fires: int
    total_modis: int = 0
    total_viirs: int = 0
    sensors_used: list[str]
    scaling_ratio: float = 1.0   # <-- AJOUT
    generated_at: str


class FirePoint(BaseModel):
    latitude: float
    longitude: float
    acq_date: str
    acq_time: str | None = None
    sensor: str
    confidence: str
    frp: float | None = None
    detection_type: int | None = None
    region: str | None = None  # <-- Optionnel : "Littoral", "Centre", etc.


class RealtimeResponse(BaseModel):
    zone: str
    days: int
    count: int
    fires: list[FirePoint]
    generated_at: str