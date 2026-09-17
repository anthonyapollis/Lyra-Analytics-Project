"""
build_facility_map.py
Builds map.html, the interactive facility intelligence map, from the warehouse CSVs.

Every number on the page is aggregated here from DimFacilityGeography and
FactCounsellingSessions, so the map cannot drift from the data.

Location note: the Latitude/Longitude columns in DimFacilityGeography fail
validation (every facility, in every country, sits between 4 and 14 degrees),
and the recorded province/state often contradicts the recorded city. City is
the only location field that is consistent with the country, so each facility
is placed at its city centre with a small deterministic offset, and the page
says so in its Data quality tab.
"""
import json, math
from pathlib import Path
import pandas as pd

BASE = Path(__file__).parent.parent
FACTS = BASE / "data" / "facts"
OUT = BASE / "map.html"

# City centres (WGS84) and the province/state each city actually lies in.
CITIES = {
    "Cape Town": (-33.9249, 18.4241, "Western Cape"), "Durban": (-29.8587, 31.0218, "KwaZulu-Natal"),
    "Johannesburg": (-26.2041, 28.0473, "Gauteng"), "Pretoria": (-25.7479, 28.2293, "Gauteng"),
    "Bloemfontein": (-29.0852, 26.1596, "Free State"),
    "Seattle": (47.6062, -122.3321, "Washington"), "New York": (40.7128, -74.0060, "New York"),
    "Miami": (25.7617, -80.1918, "Florida"), "Los Angeles": (34.0522, -118.2437, "California"),
    "Austin": (30.2672, -97.7431, "Texas"),
    "Cardiff": (51.4816, -3.1791, "Wales"), "Manchester": (53.4808, -2.2426, "England"),
    "Belfast": (54.5973, -5.9301, "Northern Ireland"), "London": (51.5072, -0.1276, "England"),
    "Edinburgh": (55.9533, -3.1883, "Scotland"),
    "Ottawa": (45.4215, -75.6972, "Ontario"), "Vancouver": (49.2827, -123.1207, "British Columbia"),
    "Toronto": (43.6532, -79.3832, "Ontario"), "Calgary": (51.0447, -114.0719, "Alberta"),
    "Montreal": (45.5019, -73.5674, "Quebec"),
    "Perth": (-31.9523, 115.8613, "Western Australia"), "Melbourne": (-37.8136, 144.9631, "Victoria"),
    "Sydney": (-33.8688, 151.2093, "New South Wales"), "Adelaide": (-34.9285, 138.6007, "South Australia"),
    "Brisbane": (-27.4698, 153.0251, "Queensland"),
}

# South African towns without a facility, used by the coverage-gap tool.
SA_TOWNS = [
    ("Polokwane", -23.9045, 29.4689), ("Mbombela", -25.4658, 30.9853), ("Kimberley", -28.7282, 24.7499),
    ("Mahikeng", -25.8652, 25.6442), ("Rustenburg", -25.6676, 27.2421), ("Gqeberha", -33.9608, 25.6022),
    ("East London", -33.0153, 27.9116), ("Mthatha", -31.5889, 28.7844), ("George", -33.9630, 22.4617),
    ("Upington", -28.4478, 21.2561), ("Pietermaritzburg", -29.6006, 30.3794), ("Richards Bay", -28.7807, 32.0383),
    ("Newcastle", -27.7577, 29.9318), ("Welkom", -27.9774, 26.7351), ("Emalahleni", -25.8713, 29.2332),
    ("Vereeniging", -26.6731, 27.9261), ("Klerksdorp", -26.8521, 26.6667), ("Potchefstroom", -26.7145, 27.0970),
    ("Stellenbosch", -33.9321, 18.8602), ("Paarl", -33.7342, 18.9621), ("Worcester", -33.6465, 19.4485),
    ("Knysna", -34.0363, 23.0471), ("Oudtshoorn", -33.5907, 22.2014), ("Beaufort West", -32.3567, 22.5830),
    ("Springbok", -29.6643, 17.8865), ("Makhanda", -33.3042, 26.5328), ("Komani", -31.8976, 26.8753),
    ("Harrismith", -28.2728, 29.1295), ("Bethlehem", -28.2308, 28.3071), ("Tzaneen", -23.8332, 30.1635),
    ("Thohoyandou", -22.9456, 30.4849), ("Musina", -22.3395, 30.0417), ("Lephalale", -23.6794, 27.7449),
    ("Secunda", -26.5500, 29.1700), ("Ermelo", -26.5333, 29.9833), ("Port Shepstone", -30.7414, 30.4550),
    ("Vryburg", -26.9564, 24.7285), ("De Aar", -30.6497, 24.0123), ("Kuruman", -27.4524, 23.4325),
]


def main():
    geo = pd.read_csv(FACTS / "DimFacilityGeography.csv")
    unknown = sorted(set(geo.City) - set(CITIES))
    if unknown:
        raise SystemExit(f"Cities without coordinates: {unknown}")

    cols = ["FacilityKey", "Visit_Date", "ClientCompanyName", "IssueGroup", "SessionDurationMinutes",
            "RiskLevel", "FollowUpRequiredFlag", "EmergencyEscalationFlag", "CaseResolvedFlag",
            "SessionCount", "RevenueAmountZAR"]
    fact = pd.read_csv(FACTS / "FactCounsellingSessions.csv", usecols=cols)
    fact["Year"] = fact.Visit_Date.str[:4].astype(int)
    fact["HighRisk"] = fact.RiskLevel.isin(["High", "Critical"]).astype(int)

    years = sorted(fact.Year.unique().tolist())
    clients = sorted(fact.ClientCompanyName.unique().tolist())
    groups = ["Mental Health", "Workplace Wellbeing", "Work Life", "Personal Wellbeing", "Crisis"]
    assert set(fact.IssueGroup.unique()) == set(groups)

    # Facilities: city placement on a golden-angle spiral so co-located sites stay separable.
    geo = geo.sort_values("FacilityKey").reset_index(drop=True)
    geo["cityRank"] = geo.groupby("City").cumcount()
    facilities, index_of = [], {}
    for i, r in geo.iterrows():
        lat0, lng0, true_prov = CITIES[r.City]
        k = int(r.cityRank)
        radius_km = 2.2 * math.sqrt(k + 1)
        angle = k * 2.399963
        lat = lat0 + radius_km / 111.0 * math.cos(angle)
        lng = lng0 + radius_km / (111.0 * math.cos(math.radians(lat0))) * math.sin(angle)
        index_of[r.FacilityKey] = i
        facilities.append({
            "k": int(r.FacilityKey), "lat": round(lat, 5), "lng": round(lng, 5), "cc": r.CountryCode,
            "country": r.CountryName, "city": r.City, "prov": true_prov, "recProv": r.ProvinceState,
            "type": r.LyraFacilityType, "cat": r["Facility Type"], "active": int(r.ActiveFlag),
            "priv": r.PrivacyRegime,
        })

    # Facility x year x client cube: [facility, year, client, sessions, escalations, resolved,
    # high/critical risk, follow-ups, revenue ZAR (thousands), duration minutes].
    fact["fi"] = fact.FacilityKey.map(index_of)
    fact["yi"] = fact.Year.map({y: i for i, y in enumerate(years)})
    fact["ci"] = fact.ClientCompanyName.map({c: i for i, c in enumerate(clients)})
    cube = (fact.groupby(["fi", "yi", "ci"])
                .agg(n=("SessionCount", "sum"), esc=("EmergencyEscalationFlag", "sum"),
                     res=("CaseResolvedFlag", "sum"), hi=("HighRisk", "sum"),
                     fu=("FollowUpRequiredFlag", "sum"), rev=("RevenueAmountZAR", "sum"),
                     dur=("SessionDurationMinutes", "sum"))
                .reset_index())
    cube["rev"] = (cube.rev / 1000).round().astype(int)
    flat = cube[["fi", "yi", "ci", "n", "esc", "res", "hi", "fu", "rev", "dur"]].astype(int).values.ravel().tolist()

    mix = fact.groupby(["fi", "IssueGroup"]).size().unstack(fill_value=0)[groups]
    for fi, row in mix.iterrows():
        facilities[int(fi)]["mix"] = [int(v) for v in row.tolist()]

    # Checks: the cube must reproduce the fact table exactly.
    assert cube.n.sum() == fact.SessionCount.sum()
    assert cube.esc.sum() == fact.EmergencyEscalationFlag.sum()
    assert len(facilities) == len(geo) and all("mix" in f for f in facilities)

    za = geo[geo.CountryCode == "ZA"]
    city_prov = {c: v[2] for c, v in CITIES.items()}
    dq = {
        "facilities": int(len(geo)),
        "coordRange": [round(float(geo.Latitude.min()), 2), round(float(geo.Latitude.max()), 2),
                       round(float(geo.Longitude.min()), 2), round(float(geo.Longitude.max()), 2)],
        "provMismatch": int((geo.City.map(city_prov) != geo.ProvinceState).sum()),
        "provMismatchZA": int((za.City.map(city_prov) != za.ProvinceState).sum()),
        "facilitiesZA": int(len(za)),
        "sessions": int(fact.SessionCount.sum()),
        "dateFrom": fact.Visit_Date.min(), "dateTo": fact.Visit_Date.max(),
    }

    payload = {"years": years, "clients": clients, "groups": groups, "facilities": facilities,
               "cube": flat, "towns": SA_TOWNS, "dq": dq}
    html = TEMPLATE.replace("/*__DATA__*/null", json.dumps(payload, separators=(",", ":")))
    OUT.write_text(html, encoding="utf-8")
    print(f"map.html written: {len(facilities)} facilities, {len(cube):,} cube rows, "
          f"{dq['sessions']:,} sessions, {OUT.stat().st_size/1024:.0f} KB")


TEMPLATE = (Path(__file__).parent / "facility_map_template.html").read_text(encoding="utf-8")

if __name__ == "__main__":
    main()
