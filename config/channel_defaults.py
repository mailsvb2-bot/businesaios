from dataclasses import dataclass

CANON_COMPAT_SHIM = True


@dataclass(frozen=True)
class ChannelDefaults:
    ads: object = 'enabled'
    seo: object = 'enabled'
    platforms: object = 'enabled'
