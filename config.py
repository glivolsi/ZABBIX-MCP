from pydantic_settings import BaseSettings
from typing import Optional
from pydantic import ConfigDict

class Settings(BaseSettings):
    model_config = ConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore"  # ⬅️ PERMETTE CAMPI EXTRA
    )
    
    zabbix_url: str
    zabbix_api_token: Optional[str] = None
    zabbix_user: Optional[str] = None
    zabbix_password: Optional[str] = None
    zabbix_verify_ssl: bool = True
    zabbix_readonly: bool = False
    
    server_host: str = "0.0.0.0"
    server_port: int = 8000
    session_timeout: int = 3600

settings = Settings()