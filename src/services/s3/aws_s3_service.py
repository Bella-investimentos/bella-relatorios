import boto3
from botocore.exceptions import ClientError
import os
from io import BytesIO

AWS_KEY = os.getenv("AWS_KEY")
AWS_SECRET = os.getenv("AWS_SECRET")

s3 = boto3.client(
    "s3",
    aws_access_key_id=AWS_KEY,
    aws_secret_access_key=AWS_SECRET,
    region_name="us-east-1"
)

def upload_pdf_to_s3(buffer: BytesIO, key: str, bucket: str) -> str:
    # Verifica se o arquivo já existe
    try:
        s3.head_object(Bucket=bucket, Key=key)
        # Se não lançar exceção, o arquivo existe — deletar
        s3.delete_object(Bucket=bucket, Key=key)
    except ClientError as e:
        # Se não existe (404), continua normalmente
        if e.response['Error']['Code'] != '404':
            raise

    # ✅ Upload do novo arquivo - preservando o buffer original
    buffer.seek(0)
    
    # ✅ Criar cópia dos dados antes do upload
    buffer_data = buffer.read()
    buffer.seek(0)  # Retornar ao início para o caller
    
    # ✅ Usar BytesIO temporário para o upload
    temp_buffer = BytesIO(buffer_data)
    s3.upload_fileobj(temp_buffer, bucket, key, ExtraArgs={"ContentType": "application/pdf"})
    temp_buffer.close()  # Fechar apenas o temporário

    return key

def upload_bytes_to_s3(buffer: BytesIO, key: str, bucket: str, content_type: str) -> str:
    """
    Faz upload de bytes (buffer) para o S3 com Content-Type informado.
    Se o objeto já existir, apaga antes.
    """
    # verifica existência
    try:
        s3.head_object(Bucket=bucket, Key=key)
        s3.delete_object(Bucket=bucket, Key=key)
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") != "404":
            raise

    # Upload - preservando o buffer original
    buffer.seek(0)
    
    # Criar cópia dos dados antes do upload
    buffer_data = buffer.read()
    buffer.seek(0)  # Retornar ao início para o caller
    
    # Usar BytesIO temporário para o upload
    temp_buffer = BytesIO(buffer_data)
    s3.upload_fileobj(temp_buffer, bucket, key, ExtraArgs={"ContentType": content_type})
    temp_buffer.close()  # Fechar apenas o temporário
    
    return key

def generate_temporary_url(key: str, bucket: str) -> str:
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=15 * 60 # 15 minutos
    )