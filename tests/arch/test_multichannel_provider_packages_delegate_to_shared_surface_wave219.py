from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE_INIT_FILES=(
    ROOT / 'interfaces/messaging/whatsapp/__init__.py',
    ROOT / 'interfaces/messaging/sms/__init__.py',
    ROOT / 'interfaces/messaging/email/__init__.py',
    ROOT / 'interfaces/messaging/instagram/__init__.py',
    ROOT / 'interfaces/messaging/messenger/__init__.py',
    ROOT / 'interfaces/regional/line/__init__.py',
    ROOT / 'interfaces/regional/wechat/__init__.py',
    ROOT / 'interfaces/regional/kakaotalk/__init__.py',
    ROOT / 'interfaces/regional/viber/__init__.py',
)

def test_provider_packages_delegate_via_install_channel_package_namespace():
    offenders=[]
    for path in PACKAGE_INIT_FILES:
        text=path.read_text(encoding='utf-8')
        if 'install_channel_package_namespace' not in text:
            offenders.append(path.as_posix())
    assert not offenders, offenders

def test_provider_packages_keep_provider_triplet_declared():
    offenders=[]
    for path in PACKAGE_INIT_FILES:
        text=path.read_text(encoding='utf-8')
        required=('PROVIDER =','ENV_PREFIX =','DEFAULT_MODE =')
        missing=[item for item in required if item not in text]
        if missing:
            offenders.append(f'{path.as_posix()}: missing {missing}')
    assert not offenders, offenders
