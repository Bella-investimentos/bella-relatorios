"""
AWS Lambda handler for Portfolio API
"""
import os
import sys

# Adicionar o diretório atual ao path
sys.path.append(os.path.dirname(os.path.realpath(__file__)))

from mangum import Mangum
from src.api.main import app

# Handler para Lambda
handler = Mangum(app, lifespan="off")

def lambda_handler(event, context):
    """AWS Lambda handler function"""
    return handler(event, context)