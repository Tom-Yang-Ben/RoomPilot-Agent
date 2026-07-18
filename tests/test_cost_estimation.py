from roompilot.server.cost_estimation import estimate_project_cost, load_default_cost_catalog


def test_sourced_rates_produce_traceable_low_base_high_concept_estimate() -> None:
    catalog = {
        "catalog_version": "2026-07-12",
        "currency": "TWD",
        "region": "台灣",
        "rates": [
            {
                "work_code": "wall_wrap.carpentry",
                "unit": "m",
                "range_twd": {"low": 1312, "base": 2459, "high": 3608},
                "source_ids": ["uptogo-wall-wrap-2026"],
                "valid_as_of": "2026-07-12",
                "inclusions": ["基本木作與材料"],
                "exclusions": ["拆除", "清運", "機電移位", "稅金"],
            },
            {
                "work_code": "electrical.outlet_relocation",
                "unit": "point",
                "range_twd": {"low": 300, "base": 650, "high": 1000},
                "source_ids": ["945-outlet-2026"],
                "valid_as_of": "2026-03-24",
                "inclusions": ["基本安裝或更換"],
                "exclusions": ["鑿牆", "長距離拉線", "配電盤修改"],
            },
        ],
        "sources": [
            {"id": "uptogo-wall-wrap-2026", "publisher": "UpToGo", "url": "https://uptogo.com.tw/example", "retrieved_on": "2026-07-12"},
            {"id": "945-outlet-2026", "publisher": "找師傅", "url": "https://www.945.com.tw/example", "retrieved_on": "2026-07-12"},
        ],
    }
    report = estimate_project_cost(
        [
            {
                "id": "change-wall-01",
                "work_code": "wall_wrap.carpentry",
                "description": "主臥樑柱包覆 3.6 公尺",
                "quantity": {"value": 3.6, "unit": "m"},
                "quantity_evidence": ["change-wall-01", "column-1"],
            },
            {
                "id": "change-outlet-01",
                "work_code": "electrical.outlet_relocation",
                "description": "插座移位 2 點",
                "quantity": {"value": 2, "unit": "point"},
                "quantity_evidence": ["change-outlet-01", "outlet-3"],
            },
        ],
        catalog=catalog,
    )

    assert report["totals_twd"] == {"low": 5323, "base": 10152, "high": 14989}
    assert report["items"][0]["source_ids"] == ["uptogo-wall-wrap-2026"]
    assert report["items"][1]["estimate_twd"] == {"low": 600, "base": 1300, "high": 2000}
    assert report["items"][1]["exclusions"] == ["鑿牆", "長距離拉線", "配電盤修改"]
    assert report["status"] == "concept_estimate"
    assert report["disclaimer_zh"] == "網路公開行情概算；施工前須現場丈量並取得正式報價。"


def test_default_online_price_seed_keeps_source_links_and_explicit_exclusions() -> None:
    catalog = load_default_cost_catalog()

    assert catalog["region"] == "台灣"
    assert all(source["url"].startswith("https://") for source in catalog["sources"])
    assert all(source["retrieved_on"] == "2026-07-12" for source in catalog["sources"])
    assert all(rate["inclusions"] and rate["exclusions"] for rate in catalog["rates"])
