from __future__ import annotations


def build_business_autonomy_guarded_service(*args, **kwargs):
    from runtime.business_autonomy.bootstrap import build_business_autonomy_guarded_service as _impl
    return _impl(*args, **kwargs)


def build_business_autonomy_operationalization(*args, **kwargs):
    from runtime.business_autonomy.public_api import build_business_autonomy_operationalization as _impl
    return _impl(*args, **kwargs)


__all__ = ["build_business_autonomy_guarded_service", "build_business_autonomy_operationalization"]
