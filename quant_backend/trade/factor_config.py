import json


VISIBLE_BUILTIN_FACTORS = [
    {
        "code": "mom_20",
        "name": "20日动量",
        "description": "近20个交易日收益率，偏中期趋势",
        "default_weight": 0.45,
        "enabled": True,
    },
    {
        "code": "rev_5",
        "name": "5日反转",
        "description": "近5个交易日收益率取反，短期回调加分",
        "default_weight": 0.1,
        "enabled": True,
    },
    {
        "code": "vol_20",
        "name": "20日低波动",
        "description": "近20个交易日收益波动率取反，波动越小越好",
        "default_weight": 0.2,
        "enabled": True,
    },
    {
        "code": "trend_20",
        "name": "20日均线趋势",
        "description": "收盘价相对20日均线的偏离，强于均线加分",
        "default_weight": 0.25,
        "enabled": True,
    },
]

LEGACY_FACTORS = [
    {
        "code": "mom_1",
        "name": "1日动量",
        "description": "旧版单日涨跌幅因子",
        "default_weight": 0.0,
        "enabled": False,
    },
    {
        "code": "bias_5",
        "name": "5日均线偏离",
        "description": "旧版5日均线偏离因子",
        "default_weight": 0.0,
        "enabled": False,
    },
]

BUILTIN_FACTOR_MAP = {
    item["code"]: item for item in [*VISIBLE_BUILTIN_FACTORS, *LEGACY_FACTORS]
}

DEFAULT_STRATEGY_CONFIG = {
    "top_n": 5,
    "buy_threshold": 0.3,
    "allow_cash": True,
    "fee_rate": 0.0001,
    "min_fee": 0.0,
    "factors": [
        {
            "code": item["code"],
            "weight": item["default_weight"],
            "enabled": item["enabled"],
        }
        for item in VISIBLE_BUILTIN_FACTORS
    ],
}


def _to_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_bool(value, default=False):
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on", "是", "启用"}
    return bool(value)


def load_config(raw_config=None):
    if raw_config is None or raw_config == "":
        return {}
    if isinstance(raw_config, dict):
        return raw_config
    if isinstance(raw_config, str):
        try:
            return json.loads(raw_config)
        except json.JSONDecodeError:
            return {}
    return {}


def build_legacy_config(config):
    weight_mom = _to_float(config.get("weight_mom"), 0.5)
    weight_bias = _to_float(config.get("weight_bias"), 0.5)
    top_n = max(1, _to_int(config.get("top_n"), 2))

    return {
        "top_n": top_n,
        "buy_threshold": -999999.0,
        "allow_cash": False,
        "fee_rate": _to_float(config.get("fee_rate"), 0.0001),
        "min_fee": _to_float(config.get("min_fee"), 0.0),
        "factors": [
            {"code": "mom_1", "weight": weight_mom, "enabled": weight_mom != 0},
            {"code": "bias_5", "weight": weight_bias, "enabled": weight_bias != 0},
        ],
    }


def normalize_strategy_config(raw_config=None, legacy_params=None):
    config = load_config(raw_config)
    if legacy_params:
        config = {**legacy_params, **config}

    # 兼容旧版：没有 factors，但包含 weight_mom / weight_bias。
    if "factors" not in config and ("weight_mom" in config or "weight_bias" in config):
        return build_legacy_config(config)

    default = DEFAULT_STRATEGY_CONFIG
    top_n = max(1, _to_int(config.get("top_n"), default["top_n"]))
    raw_factors = config.get("factors") or default["factors"]
    factors = []
    seen = set()
    for item in raw_factors:
        code = str(item.get("code", "")).strip()
        if code not in BUILTIN_FACTOR_MAP or code in seen:
            continue
        seen.add(code)
        weight = _to_float(item.get("weight"), BUILTIN_FACTOR_MAP[code].get("default_weight", 0.0))
        enabled = _to_bool(item.get("enabled"), True)
        factors.append({"code": code, "weight": weight, "enabled": enabled})

    if not factors:
        factors = [dict(item) for item in default["factors"]]

    return {
        "top_n": top_n,
        "buy_threshold": _to_float(config.get("buy_threshold"), default["buy_threshold"]),
        "allow_cash": _to_bool(config.get("allow_cash"), default["allow_cash"]),
        "fee_rate": max(0.0, _to_float(config.get("fee_rate"), default["fee_rate"])),
        "min_fee": max(0.0, _to_float(config.get("min_fee"), default["min_fee"])),
        "factors": factors,
    }


def get_enabled_factors(config):
    return [
        item for item in config.get("factors", [])
        if item.get("enabled") and abs(_to_float(item.get("weight"), 0.0)) > 1e-12
    ]


def max_lookback_for_factors(factors):
    lookbacks = {
        "mom_20": 21,
        "rev_5": 6,
        "vol_20": 21,
        "trend_20": 20,
        "mom_1": 2,
        "bias_5": 5,
    }
    if not factors:
        return 21
    return max(lookbacks.get(item["code"], 21) for item in factors)
