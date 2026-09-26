import pytest
from bot import compose

def test_compose_dentist_merchant():
    cat = {"slug": "dentists"}
    m = {
        "merchant_id": "m_001",
        "category_slug": "dentists",
        "identity": {"name": "Dr. Meera Clinic", "owner_first_name": "Meera", "locality": "Lajpat Nagar"},
        "customer_aggregate": {"high_risk_adult_count": 124}
    }
    t = {"id": "trg_001", "kind": "research_digest", "scope": "merchant"}
    
    res = compose(cat, m, t)
    assert res["send_as"] == "vera"
    assert "Dr. Meera" in res["body"]
    assert "JIDA" in res["body"]
    assert "124" in res["body"]
    assert "http" not in res["body"]
    assert res["cta"] is not None

def test_compose_dentist_customer():
    cat = {"slug": "dentists"}
    m = {
        "merchant_id": "m_001",
        "category_slug": "dentists",
        "identity": {"name": "Dr. Meera Clinic", "owner_first_name": "Meera", "locality": "Lajpat Nagar"}
    }
    t = {
        "id": "trg_003",
        "kind": "recall_due",
        "scope": "customer",
        "payload": {"available_slots": [{"label": "Wed 5 Nov, 6pm"}, {"label": "Thu 6 Nov, 5pm"}]}
    }
    c = {"customer_id": "c_001", "identity": {"name": "Priya", "language_pref": "hi-en mix"}}

    res = compose(cat, m, t, c)
    assert res["send_as"] == "merchant_on_behalf"
    assert "Priya" in res["body"]
    assert "Wed 5 Nov" in res["body"]
    assert "http" not in res["body"]

def test_compose_salon():
    cat = {"slug": "salons"}
    m = {
        "merchant_id": "m_003",
        "category_slug": "salons",
        "identity": {"name": "Studio11", "owner_first_name": "Lakshmi", "locality": "Kapra"}
    }
    t = {"id": "trg_008", "kind": "curious_ask_due", "scope": "merchant"}

    res = compose(cat, m, t)
    assert res["send_as"] == "vera"
    assert "Lakshmi" in res["body"]
    assert "Studio11" in res["body"]

def test_compose_restaurant():
    cat = {"slug": "restaurants"}
    m = {
        "merchant_id": "m_005",
        "category_slug": "restaurants",
        "identity": {"name": "SK Pizza", "owner_first_name": "Suresh", "locality": "Sant Nagar"}
    }
    t = {"id": "trg_010", "kind": "ipl_match_today", "scope": "merchant", "payload": {"match": "DC vs MI", "stadium": "Arun Jaitley"}}

    res = compose(cat, m, t)
    assert res["send_as"] == "vera"
    assert "Suresh" in res["body"]
    assert "IPL" in res["body"] or "DC vs MI" in res["body"]

def test_compose_gym():
    cat = {"slug": "gyms"}
    m = {
        "merchant_id": "m_007",
        "category_slug": "gyms",
        "identity": {"name": "PowerHouse", "owner_first_name": "Karthik", "locality": "HSR Layout"}
    }
    t = {"id": "trg_015", "kind": "customer_lapsed_hard", "scope": "customer"}
    c = {"customer_id": "c_010", "identity": {"name": "Rashmi"}}

    res = compose(cat, m, t, c)
    assert res["send_as"] == "merchant_on_behalf"
    assert "Rashmi" in res["body"]
    assert "Karthik" in res["body"]

def test_compose_pharmacy():
    cat = {"slug": "pharmacies"}
    m = {
        "merchant_id": "m_009",
        "category_slug": "pharmacies",
        "identity": {"name": "Apollo Pharmacy", "owner_first_name": "Ramesh", "locality": "Malviya Nagar"}
    }
    t = {"id": "trg_019", "kind": "chronic_refill_due", "scope": "customer"}
    c = {"customer_id": "c_013", "identity": {"name": "Sharma", "language_pref": "hi"}}

    res = compose(cat, m, t, c)
    assert res["send_as"] == "merchant_on_behalf"
    assert "Sharma" in res["body"]
    assert "Namaste" in res["body"]

def test_determinism():
    cat = {"slug": "dentists"}
    m = {
        "merchant_id": "m_001",
        "category_slug": "dentists",
        "identity": {"name": "Dr. Meera Clinic", "owner_first_name": "Meera"}
    }
    t = {"id": "trg_001", "kind": "research_digest", "scope": "merchant"}
    
    res1 = compose(cat, m, t)
    res2 = compose(cat, m, t)
    assert res1 == res2
