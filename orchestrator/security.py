import hashlib,hmac

def verify_github_signature(secret:str,body:bytes,signature:str|None)->bool:
    if not secret or not signature or not signature.startswith("sha256="): return False
    expected="sha256="+hmac.new(secret.encode(),body,hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected,signature)

def verify_bearer(expected:str,auth:str|None)->bool:
    if not expected or not auth: return False
    scheme,_,token=auth.partition(" ")
    return scheme.lower()=="bearer" and hmac.compare_digest(expected,token)
