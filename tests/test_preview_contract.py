from scripts.quick_preview import public_tunnel_url

def test_api_error_url_is_not_a_public_preview():
    assert public_tunnel_url('Post "https://api.trycloudflare.com/tunnel": network is unreachable') is None

def test_generated_tunnel_hostname_is_recognized():
    assert public_tunnel_url('Your quick Tunnel: https://synthetic-check-not-real.trycloudflare.com')=='https://synthetic-check-not-real.trycloudflare.com'

def test_no_tunnel_success_is_invented():
    assert public_tunnel_url('DNS failed. No public hostname was assigned.') is None
