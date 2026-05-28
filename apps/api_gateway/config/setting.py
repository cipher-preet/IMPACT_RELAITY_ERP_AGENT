from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict



class Settings(BaseSettings):
    APP_NAME: str = "AI Agent API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    OPENAI_API_KEY: str
    NODE_MCP_SERVER_URL: str
    ASSISTANT_MCP_SERVER_TOKEN: str
    
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

    # class Config:
    #     env_file = ".env"


settings = Settings()