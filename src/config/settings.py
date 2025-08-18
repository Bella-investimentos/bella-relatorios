# config/settings.py
import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    FMP_API_KEY = os.getenv("FMP_API_KEY")
    REQUEST_TIMEOUT = 20
    CHART_OUTPUT_DIR = "static/charts"
    ANTIFRAGILE_MULTIPLIER = 1.03
    WEEKLY_GROUPING_DAYS = 5

settings = Settings()