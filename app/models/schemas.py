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
    # Trois matrices : combinée, MODIS seul, VIIRS seul
    matrix: list[list[int]]
    matrix_modis: list[list[int]]
    matrix_viirs: list[list[int]]
    # Première année où VIIRS est présent (None si aucune)
    first_viirs_year: int | None = None
    # Statistiques mensuelles
    median_by_month: list[float]
    current_year: int
    current_month: int
    current_count: int
    median_for_current_month: float
    current_anomaly_pct: float
    # Totaux
    total_fires: int
    total_modis: int = 0
    total_viirs: int = 0
    sensors_used: list[str]
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


class RealtimeResponse(BaseModel):
    zone: str
    days: int
    count: int
    fires: list[FirePoint]
    generated_at: str