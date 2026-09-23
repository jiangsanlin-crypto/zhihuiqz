import hashlib,hmac
from orchestrator.security import verify_bearer,verify_github_signature
def test_signature():
    body=b'{"ok":true}'; secret="abc"
    sig="sha256="+hmac.new(secret.encode(),body,hashlib.sha256).hexdigest()
    assert verify_github_signature(secret,body,sig)
    assert not verify_github_signature(secret,body,"sha256=bad")
def test_bearer():
    assert verify_bearer("token","Bearer token")
    assert not verify_bearer("token","Bearer other")
