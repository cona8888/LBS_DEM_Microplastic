"""Add the 10 November capillary measurements to the source and observation tables."""
import csv

STUDIES = {
    "10.1016/j.powtec.2017.02.053": (
        "LV17", "Liévano, Velankar and McCarthy (2017), Powder Technology",
        "Ethylene glycol between acrylic spheres", "Future 3D force comparison",
        "Total force in µN. A 2D line force cannot be substituted."),
    "10.1017/jfm.2026.12035": (
        "BT26", "Bokányi-Tóth et al. (2026), Journal of Fluid Mechanics",
        "Silicone oil between horizontal copper cylinders", "Gravity-aware geometry input",
        "Zero-voltage area is an imposed input for a future shape test. Other rows include an electric field."),
}
ROLES = {
    "independent_3D_force_only": "RESERVED_3D_FORCE",
    "geometry_input_for_independent_profile": "GEOMETRY_INPUT",
    "electric_field_outside_model": "OUTSIDE_MODEL",
}


def add_capillary_references(db, csv_path):
    with csv_path.open(newline="", encoding="utf-8") as f:
        records = list(csv.DictReader(f))
    source_ids = {}
    for doi, (key, citation, material, intended, limits) in STUDIES.items():
        found = db.execute("SELECT source_id FROM sources WHERE doi=?", (doi,)).fetchone()
        if found:
            source_ids[doi] = found[0]
            continue
        source_ids[doi] = key
        db.execute("INSERT INTO sources VALUES(?,?,?,?,?,?,?,?,?)", (
            key, "Capillarity", citation, doi, "https://doi.org/"+doi,
            "Consensus discovery, primary figure/table extraction", material, intended, limits))
    for row in records:
        doi = row["study_doi"]
        role = ROLES[row["benchmark_scope"]]
        is_graph = row["extraction"] == "visual_series_centre_approx"
        conditions = [f"R={row['radius_mm']} mm", f"gap={row['gap_mm']} mm"]
        if row["volume_uL"]:
            conditions.append(f"V={row['volume_uL']} µL")
        if row["voltage_V"]:
            conditions.append(f"electric potential={row['voltage_V']} V")
        db.execute("INSERT INTO observations VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            row["record_id"], source_ids[doi], row["geometry"], row["observable"],
            float(row["value"]), row["unit"], "~" if is_graph else "=",
            float(row["reading_allowance_original"])*0.048*float(row["radius_mm"])*1000 if is_graph else None,
            "Graph-reading allowance in µN" if is_graph else None,
            "Graph-read experimental landmark" if is_graph else "Tabulated photo-derived area",
            role, ", ".join([row["liquid"], row["solid"], *conditions]),
            row["source_location"], "https://doi.org/"+doi, "2026-11-10 capillary supplement"))
    db.executemany("UPDATE settings SET value=? WHERE name=?", [
        ("2026-11-10","snapshot"), ("1.1","version"),
        ("Frozen calibration plus traceable capillary references for different geometries.","scope")])
    return len(records)
