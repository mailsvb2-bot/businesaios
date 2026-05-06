from security.governance_owner_factory import build_security_governance_infrastructure


def test_crypto_agility_profiles_exist(tmp_path):
    owner = build_security_governance_infrastructure(base_dir=tmp_path, shared_secret='secret')
    profiles = {item.profile_name for item in owner.crypto_agility.list_profiles()}
    assert {'default-sealed-box', 'regulated-aes-gcm'} <= profiles
    profile = owner.crypto_agility.get('regulated-aes-gcm')
    assert profile.encryption_algorithm == 'aes256_gcm'
