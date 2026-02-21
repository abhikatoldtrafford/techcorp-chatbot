from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    OPENAI_API_KEY: str
    OPENAI_MODEL: str = "gpt-5-mini"
    MCP_SERVER_URL: str = "https://vipfapwm3x.us-east-1.awsapprunner.com/mcp"
    MAX_COMPLETION_TOKENS: int = 4096
    MAX_TOOL_CALLS_PER_TURN: int = 8
    MAX_CONVERSATION_TURNS: int = 50
    MAX_HISTORY_TURNS: int = 5


settings = Settings()
