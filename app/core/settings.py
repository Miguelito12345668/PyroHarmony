from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    firms_map_key: str = ""
    cache_dir: Path = Path("./cache")
    cache_ttl_seconds: int = 21600
    start_year: int = 2000
    zones_config_path: Path = Path("app/config/zones.json")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

settings = Settings()