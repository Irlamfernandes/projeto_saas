import os
import unicodedata
import requests

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

def limpar_nome_arquivo(nome):
    nfkd = unicodedata.normalize('NFKD', nome)
    sem_acento = "".join([c for c in nfkd if not unicodedata.combining(c)])
    return sem_acento.replace(" ", "_")

def upload_imagem_supabase(file_obj, produto_id):
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise Exception("Credenciais do Supabase não configuradas no .env.")
    
    try:
        base_url = SUPABASE_URL.strip().rstrip('/')
        if base_url.endswith('/rest/v1'):
            base_url = base_url[:-8]
            
        nome_arquivo_limpo = limpar_nome_arquivo(getattr(file_obj, 'name', 'arquivo'))
        file_path = f"{produto_id}/{nome_arquivo_limpo}"
        
        file_bytes = file_obj.read()
        content_type = getattr(file_obj, 'content_type', 'application/octet-stream')
        
        url = f"{base_url}/storage/v1/object/imagens/{file_path}"
        
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": content_type,
            "x-upsert": "true"
        }
        
        response = requests.post(url, data=file_bytes, headers=headers)
        
        if response.status_code not in (200, 201):
            raise Exception(f"Erro na API do Supabase ({response.status_code}): {response.text}")
            
        public_url = f"{base_url}/storage/v1/object/public/imagens/{file_path}"
        return public_url
        
    except Exception as e:
        raise Exception(f"Erro no Supabase Storage: {str(e)}")