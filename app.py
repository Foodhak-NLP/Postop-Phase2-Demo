"""
Phase 2 Metabolic Recovery — 30-Day Doctor-Facing Demo
=============================================================
Recipes are generated STRICTLY from KG evidence-backed ingredients.
Single patient with multiple adherence profiles.
Safety-driven fallback: safety triggers → basic recovery → step up when clear.
"""
import streamlit as st
import math, hashlib, random
from copy import deepcopy

st.set_page_config(page_title="Metabolic Recovery Plan", layout="wide", page_icon="🧬")

# ═══════════════════════════════════════════════════════════════════════════════
# DATA LAYER
# ═══════════════════════════════════════════════════════════════════════════════

DISCRETE_ACTION_SPACE = {
    0: "stabilizing_recovery_phase", 1: "metabolic_focus", 2: "lipid_focus",
    3: "inflammation_focus", 4: "nutrition_vitamins_minerals_focus",
    5: "metabolic_lipid_recovery", 6: "metabolic_inflammation_recovery",
    7: "metabolic_nutrition_recovery", 8: "lipid_inflammation_recovery",
    9: "lipid_nutrition_recovery", 10: "inflammation_nutrition_recovery",
    11: "metabolic_lipid_nutrition_recovery", 12: "metabolic_lipid_inflammation_recovery",
    13: "lipid_inflammation_nutrition_recovery",
    14: "metabolic_lipid_inflammation_nutrition_recovery",
    15: "metabolic_inflammation_nutrition_recovery",
}

ACTION_TO_MAIN_CLUSTERS = {
    0: [], 1: ["metabolic"], 2: ["lipids"], 3: ["inflammation"],
    4: ["nutrition_vitamins_minerals"], 5: ["metabolic","lipids"],
    6: ["metabolic","inflammation"], 7: ["metabolic","nutrition_vitamins_minerals"],
    8: ["lipids","inflammation"], 9: ["lipids","nutrition_vitamins_minerals"],
    10: ["inflammation","nutrition_vitamins_minerals"],
    11: ["metabolic","lipids","nutrition_vitamins_minerals"],
    12: ["metabolic","lipids","inflammation"],
    13: ["lipids","inflammation","nutrition_vitamins_minerals"],
    14: ["metabolic","lipids","inflammation","nutrition_vitamins_minerals"],
    15: ["metabolic","inflammation","nutrition_vitamins_minerals"],
}

CLUSTER_DISPLAY = {
    "metabolic": ("🩸", "Blood Sugar & Metabolism"),
    "lipids": ("🫀", "Cholesterol & Lipids"),
    "inflammation": ("🔥", "Inflammation"),
    "nutrition_vitamins_minerals": ("💊", "Vitamins & Minerals"),
}

PLAN_DISPLAY = {
    0: "Basic recovery (safety fallback)", 1: "Blood sugar recovery",
    2: "Cholesterol recovery", 3: "Inflammation recovery",
    4: "Vitamin & mineral recovery", 5: "Blood sugar + cholesterol recovery",
    6: "Blood sugar + inflammation recovery", 7: "Blood sugar + vitamin recovery",
    8: "Cholesterol + inflammation recovery", 9: "Cholesterol + vitamin recovery",
    10: "Inflammation + vitamin recovery",
    11: "Blood sugar + cholesterol + vitamin recovery",
    12: "Blood sugar + cholesterol + inflammation recovery",
    13: "Cholesterol + inflammation + vitamin recovery",
    14: "Full metabolic recovery (all areas)",
    15: "Blood sugar + inflammation + vitamin recovery",
}

MAIN_CQL_CLUSTERS = {
    "metabolic": ["HbA1c", "insulin", "C-peptide"],
    "lipids": ["LDL cholesterol", "triglycerides", "total cholesterol", "non-HDL cholesterol"],
    "inflammation": ["hs-CRP", "homocysteine"],
    "nutrition_vitamins_minerals": ["folate", "vitamin B12", "magnesium",
                                    "transferrin saturation", "hemoglobin", "sodium"],
}

TARGET_DIRECTIONS = {
    "HbA1c": -1, "insulin": -1, "C-peptide": -1,
    "LDL cholesterol": -1, "triglycerides": -1, "total cholesterol": -1,
    "non-HDL cholesterol": -1, "hs-CRP": -1, "homocysteine": -1,
    "folate": +1, "vitamin B12": +1, "magnesium": +1,
    "transferrin saturation": +1, "hemoglobin": +1,
    "sodium": 0, "eGFR": +1, "microalbumin": -1,
    "free T3": 0, "INR": 0, "urine pH": 0,
}

BIOMARKER_TO_CLUSTER = {}
for _cl, _bios in MAIN_CQL_CLUSTERS.items():
    for _b in _bios:
        BIOMARKER_TO_CLUSTER[_b] = _cl

MACRO_BOUNDS = {
    "protein_g_per_kg": (0.8, 1.8), "carbs_pct": (25.0, 60.0),
    "fat_pct": (20.0, 45.0), "fiber_g": (12.0, 45.0),
    "saturated_fat_pct": (4.0, 13.0),
}
SURGERY_PROTEIN_CAP = {"bariatric": 1.5, "cardiac": 1.6, "orthopedic": 1.8}

# ─── Adherence profiles ──────────────────────────────────────────────────────
def _make_profile(pattern, seed=42):
    rng = random.Random(seed)
    days = []
    weights = {"well": (0.85, 0.97), "moderate": (0.45, 0.80), "low": (0.15, 0.45)}
    w, p = weights[pattern]
    for _ in range(30):
        r = rng.random()
        days.append(0 if r < w else (1 if r < p else 2))
    return days

ADHERENCE_PROFILES = {k: _make_profile(k, seed=42) for k in ["well", "moderate", "low"]}

# ─── KG ingredient pool — categorized by slot type ───────────────────────────
# Every ingredient here is KG-backed. Organized by cluster → biomarker → slot.
# Recipes will ONLY use ingredients from this pool.

KG_INGREDIENTS = {
    "metabolic": {
        "HbA1c": {
            "subjects": ["low glycemic high fiber pattern", "cinnamon supplementation",
                         "berberine", "probiotic / prebiotic / synbiotic support"],
            "by_slot": {
                "grain": ["oats", "barley", "brown rice", "whole wheat", "millet", "ragi", "bajra"],
                "legume": ["chickpeas", "green peas", "legumes", "lentils"],
                "vegetable": ["bitter gourd", "methi leaves"],
                "fruit": ["amla", "jamun"],
                "seed": ["flaxseed", "chia seeds", "psyllium husk", "fenugreek seeds"],
                "spice": ["cinnamon", "turmeric"],
                "dairy": ["yoghurt", "kefir"],
                "nut": ["almonds"],
            },
        },
        "C-peptide": {
            "subjects": ["low glycemic high fiber pattern", "probiotic / prebiotic support"],
            "by_slot": {
                "grain": ["quinoa", "brown rice", "oats"],
                "legume": ["lentils", "moong dal"],
                "vegetable": ["broccoli", "cauliflower", "bell peppers", "spinach", "kale", "sweet potato"],
                "fruit": ["avocado"],
                "nut": ["almonds", "walnuts"],
                "dairy": ["yoghurt"],
                "protein_source": ["eggs", "tofu", "paneer"],
            },
        },
        "insulin": {
            "subjects": ["cinnamon supplementation", "berberine", "chromium support"],
            "by_slot": {
                "vegetable": ["broccoli", "green beans", "mushrooms", "bitter melon"],
                "spice": ["cinnamon", "garlic", "fenugreek"],
                "nut": ["almonds", "walnuts"],
            },
        },
    },
    "lipids": {
        "LDL cholesterol": {
            "subjects": ["soluble fiber pattern", "plant sterols & stanols", "omega-3 fatty acids"],
            "by_slot": {
                "grain": ["oats", "barley"],
                "legume": ["lentils", "beans", "chickpeas", "kidney beans"],
                "vegetable": ["eggplant", "okra"],
                "fruit": ["apples", "strawberries", "citrus fruits", "avocado"],
                "nut": ["almonds", "walnuts"],
                "seed": ["flaxseed", "psyllium husk", "sesame seeds", "sunflower seeds"],
                "spice": ["garlic"],
                "dairy": ["soy milk"],
                "protein_source": ["tofu"],
            },
        },
        "triglycerides": {
            "subjects": ["omega-3 fatty acids / n-3 PUFA", "soluble fiber pattern", "beta-glucan"],
            "by_slot": {
                "grain": ["oats", "barley", "brown rice"],
                "legume": ["lentils", "beans"],
                "seed": ["flaxseed", "chia seeds"],
                "nut": ["walnuts"],
                "protein_source": ["salmon", "sardines", "mackerel", "trout", "tuna"],
            },
        },
        "total cholesterol": {
            "subjects": ["soluble fiber pattern", "plant sterols & stanols"],
            "by_slot": {
                "grain": ["oats", "barley"],
                "legume": ["lentils", "chickpeas", "kidney beans"],
                "fruit": ["avocado"],
                "nut": ["almonds"],
                "spice": ["garlic"],
                "dairy": ["soy milk"],
                "protein_source": ["tofu", "edamame"],
            },
        },
        "non-HDL cholesterol": {
            "subjects": ["soluble fiber pattern", "konjac glucomannan"],
            "by_slot": {
                "grain": ["oats"],
                "nut": ["almonds", "walnuts"],
                "seed": ["flaxseed", "chia seeds", "psyllium husk"],
            },
        },
    },
    "inflammation": {
        "hs-CRP": {
            "subjects": ["anti-inflammatory dietary pattern", "curcumin supplementation",
                         "omega-3 fatty acids (anti-inflammatory)"],
            "by_slot": {
                "vegetable": ["broccoli", "bell peppers", "tomatoes", "mushrooms", "leafy greens"],
                "fruit": ["berries", "cherries", "pomegranate"],
                "spice": ["turmeric", "ginger", "black pepper", "garlic"],
                "nut": ["walnuts"],
                "seed": ["flaxseed"],
                "dairy": ["olive oil"],
                "protein_source": ["salmon", "sardines"],
            },
        },
        "homocysteine": {
            "subjects": ["B-vitamin support", "folate / folic acid support"],
            "by_slot": {
                "grain": ["fortified cereals"],
                "legume": ["lentils", "chickpeas"],
                "vegetable": ["spinach", "asparagus", "beetroot", "leafy greens"],
                "seed": ["sunflower seeds"],
                "dairy": ["dairy products"],
                "protein_source": ["eggs", "tempeh"],
            },
        },
    },
    "nutrition_vitamins_minerals": {
        "hemoglobin": {
            "subjects": ["iron + vitamin C pairing", "nutrition vitamins minerals support"],
            "by_slot": {
                "grain": ["ragi", "bajra"],
                "legume": ["lentils", "chickpeas", "kidney beans"],
                "vegetable": ["spinach", "beetroot", "bell peppers"],
                "fruit": ["pomegranate", "amla", "dates", "dried apricots"],
                "seed": ["pumpkin seeds", "sesame seeds"],
                "spice": ["cumin", "black pepper", "turmeric"],
                "protein_source": ["tofu", "red meat"],
            },
        },
        "folate": {
            "subjects": ["folate / folic acid support", "B-vitamin support"],
            "by_slot": {
                "grain": ["fortified cereals"],
                "legume": ["lentils", "chickpeas", "kidney beans", "black-eyed peas"],
                "vegetable": ["spinach", "asparagus", "broccoli", "brussels sprouts", "beetroot"],
                "fruit": ["avocado", "papaya", "oranges"],
                "seed": ["sunflower seeds"],
                "nut": ["peanuts"],
            },
        },
        "vitamin B12": {
            "subjects": ["B-vitamin support", "vitamin D support"],
            "by_slot": {
                "grain": ["fortified cereals"],
                "dairy": ["dairy products", "fortified soy milk"],
                "protein_source": ["eggs", "sardines", "tempeh"],
            },
        },
        "magnesium": {
            "subjects": ["nutrition vitamins minerals support"],
            "by_slot": {
                "grain": ["quinoa"],
                "legume": ["black beans", "edamame"],
                "vegetable": ["spinach"],
                "fruit": ["avocado"],
                "nut": ["almonds", "cashews"],
                "seed": ["pumpkin seeds"],
            },
        },
    },
    "stabilizing": {
        "_general": {
            "subjects": ["probiotic / prebiotic / synbiotic support", "vitamin D support"],
            "by_slot": {
                "grain": ["oats", "rice", "dalia", "ragi"],
                "legume": ["moong dal"],
                "vegetable": ["bottle gourd", "pumpkin"],
                "fruit": ["banana", "apple"],
                "nut": ["almonds"],
                "seed": ["flaxseed"],
                "spice": ["turmeric", "ginger", "cumin"],
                "dairy": ["yoghurt", "curd", "buttermilk", "warm milk"],
                "protein_source": ["paneer", "cottage cheese"],
            },
        },
    },
}

NON_VEG_TERMS = {"salmon","sardines","mackerel","herring","trout","tuna","anchovies",
    "chicken breast","fish fillet","fish","red meat","liver","clams","lamb",
    "grilled salmon","cod liver oil","eggs"}

# ─── Recipe templates ─────────────────────────────────────────────────────────
RECIPE_TEMPLATES = {
    "breakfast": [
        {"name":"{grain} porridge with {fruit} and {seed}","method":"Slow-cook {grain} with water until creamy. Top with sliced {fruit}, a teaspoon of {seed}, and a drizzle of honey.","tags":["fibre","slow-release energy"]},
        {"name":"{grain} dosa with {legume} sambhar","method":"Ferment {grain} batter overnight, make thin dosas. Serve with {legume} sambhar and coconut chutney.","tags":["low-GI","protein"]},
        {"name":"{grain} upma with {vegetable} and {spice}","method":"Dry roast {grain} semolina, temper with mustard seeds. Add chopped {vegetable} and {spice}. Steam until fluffy.","tags":["complex carbs","fibre"]},
        {"name":"Smoothie bowl: {fruit} + {seed} + {dairy}","method":"Blend frozen {fruit} with {dairy} until thick. Top with {seed} and a drizzle of honey.","tags":["antioxidant","protein"]},
        {"name":"{dairy} parfait with {fruit} and {nut}","method":"Layer {dairy} with sliced {fruit} and crushed {nut}. Add a pinch of cinnamon and honey.","tags":["probiotic","protein"]},
    ],
    "mid_morning": [
        {"name":"{vegetable} + {fruit} juice with {spice}","method":"Juice fresh {vegetable} and {fruit}. Add a pinch of {spice} and serve chilled.","tags":["vitamins","anti-inflammatory"]},
        {"name":"{nut} + {seed} trail mix","method":"Mix roasted {nut} with {seed} and a few dried berries. Portion into 30g servings.","tags":["omega-3","magnesium"]},
        {"name":"{spice} milk with {nut}","method":"Warm 200ml milk with half a teaspoon of {spice} paste. Serve with 4–5 soaked {nut}.","tags":["anti-inflammatory","calcium"]},
        {"name":"Roasted {legume} chaat with {spice}","method":"Toss roasted {legume} with chopped onion, tomato, and {spice} powder. Squeeze lemon.","tags":["protein","fibre"]},
    ],
    "lunch": [
        {"name":"{grain} + {legume} bowl with {vegetable} stir-fry","method":"Cook {grain} until fluffy. Pressure-cook {legume} with turmeric. Sauté {vegetable} in olive oil with garlic. Assemble in a bowl.","tags":["complex carbs","protein","fibre"]},
        {"name":"{protein_source} curry with {grain} and {vegetable} salad","method":"Cook {protein_source} in tomato-onion gravy with spices. Serve with steamed {grain} and chopped {vegetable} salad.","tags":["protein","iron"]},
        {"name":"{legume} soup with {grain} bread and {vegetable}","method":"Simmer {legume} with cumin, garlic, and ginger until creamy. Serve with toasted {grain} bread and steamed {vegetable}.","tags":["fibre","protein"]},
        {"name":"{vegetable} thali: {legume} dal + {grain} roti + raita","method":"Cook {legume} dal with turmeric and ghee. Make {grain} rotis. Prepare cucumber raita. Serve together.","tags":["balanced","traditional"]},
    ],
    "snack": [
        {"name":"{seed} + {spice} energy bites","method":"Blend {seed} with dates, a pinch of {spice}, and cocoa powder. Roll into balls. Refrigerate 30 min.","tags":["omega-3","fibre"]},
        {"name":"Roasted {nut} with {spice} seasoning","method":"Toss {nut} with a pinch of {spice} and sea salt. Roast at 160°C for 12 minutes.","tags":["healthy fats","magnesium"]},
        {"name":"{fruit} slices with {nut} butter","method":"Slice {fruit} and serve with a tablespoon of {nut} butter.","tags":["vitamins","protein"]},
        {"name":"{dairy} lassi with {spice}","method":"Blend {dairy} with cold water, a pinch of {spice}, and roasted cumin. Serve chilled.","tags":["probiotic","digestive"]},
    ],
    "dinner": [
        {"name":"Grilled {protein_source} with steamed {vegetable} and {grain}","method":"Marinate {protein_source} with herbs and lemon. Grill until done. Steam {vegetable} with lemon. Serve alongside {grain}.","tags":["lean protein","fibre"]},
        {"name":"{legume} khichdi with {vegetable} raita","method":"Cook {legume} and rice with turmeric, cumin, and ghee. Serve with {vegetable} raita and pickle.","tags":["gut-friendly","comfort"]},
        {"name":"{vegetable} stir-fry with {protein_source} and {grain}","method":"Stir-fry {vegetable} and {protein_source} in sesame oil with garlic and ginger. Serve with {grain}.","tags":["light","anti-inflammatory"]},
        {"name":"{protein_source} tikka with {grain} roti and {vegetable}","method":"Marinate {protein_source} in yoghurt and spices. Grill until charred. Serve with {grain} roti and sautéed {vegetable}.","tags":["protein","spiced"]},
        {"name":"{legume} and {vegetable} stew with {grain}","method":"Slow-cook {legume} with {vegetable}, tomatoes, and herbs. Serve over {grain}.","tags":["comfort","fibre"]},
    ],
}

# ─── Single demo patient ──────────────────────────────────────────────────────
DEMO_PATIENT = {
    "patient_id": "SYN-P0001", "age": 52, "sex": "M", "surgery_type": "cardiac",
    "weight_kg": 92.0, "height_cm": 172, "bmi": 31.1,
    "is_vegetarian": False, "type_2_diabetes": False,
    "phase2_entry_labs": {
        "HbA1c": 7.8, "insulin": 22.5, "C-peptide": 3.1,
        "LDL cholesterol": 155.0, "triglycerides": 210.0,
        "total cholesterol": 245.0, "non-HDL cholesterol": 175.0,
        "hs-CRP": 5.2, "homocysteine": 15.0,
        "folate": 4.5, "vitamin B12": 280.0, "magnesium": 1.75,
        "transferrin saturation": 22.0, "hemoglobin": 11.8, "sodium": 140.0,
        "eGFR": 88.0, "microalbumin": 12.0, "free T3": 2.8, "INR": 0.98, "urine pH": 6.1,
    },
    "phase1_macros": {"protein_g_per_kg": 1.2, "carbs_pct": 45.0, "fat_pct": 32.0,
                      "fiber_g": 18.0, "saturated_fat_pct": 10.0, "calories_kcal": 1850},
    "allergies": [], "medications": [],
}


# ═══════════════════════════════════════════════════════════════════════════════
# FUNCTION LAYER
# ═══════════════════════════════════════════════════════════════════════════════

def auto_doctor_targets(action_id):
    picks = {
        "metabolic": {"HbA1c": "reduce", "C-peptide": "reduce"},
        "lipids": {"LDL cholesterol": "reduce", "triglycerides": "reduce", "total cholesterol": "reduce"},
        "inflammation": {"hs-CRP": "reduce", "homocysteine": "reduce"},
        "nutrition_vitamins_minerals": {"hemoglobin": "increase", "folate": "increase"},
    }
    if action_id == 0:
        return {"hemoglobin": "increase", "folate": "increase"}
    targets = {}
    for c in ACTION_TO_MAIN_CLUSTERS[action_id]:
        targets.update(picks.get(c, {}))
    return targets


def evaluate_safety(labs):
    reasons, high_risk, organ_caution, other_caution = [], False, False, False
    checks = {
        "eGFR": {"test": lambda v: v < 60, "flag": "organ", "high": True,
                 "msg": lambda v: f"eGFR low ({v:.1f}) — avoid aggressive protein. Renal-safe constraints applied."},
        "sodium": {"test": lambda v: v < 135 or v > 145, "flag": "other", "high": True,
                   "msg": lambda v: f"Sodium abnormal ({v:.1f} mEq/L, normal 135–145) — electrolyte safety review required."},
        "INR": {"test": lambda v: v < 0.8 or v > 1.2, "flag": "other", "high": True,
                "msg": lambda v: f"INR abnormal ({v:.2f}, normal 0.8–1.2) — check medication and food-interaction risk."},
        "microalbumin": {"test": lambda v: v > 30, "flag": "organ", "high": False,
                         "msg": lambda v: f"Microalbumin elevated ({v:.1f}) — renal-safe constraints applied."},
        "free T3": {"test": lambda v: v < 2.3 or v > 4.2, "flag": "organ", "high": False,
                    "msg": lambda v: f"Free T3 outside band ({v:.2f}) — avoid aggressive calorie shifts."},
    }
    for lab_name, cfg in checks.items():
        val = labs.get(lab_name)
        if val is not None and cfg["test"](val):
            if cfg["flag"] == "organ": organ_caution = True
            else: other_caution = True
            if cfg["high"]: high_risk = True
            reasons.append(cfg["msg"](val))
    return {"high_safety_risk": high_risk, "organ_function_caution": organ_caution,
            "other_validated_caution": other_caution,
            "reasons": reasons if reasons else ["All safety checks passed."]}


def expand_macros(action_id, patient, day, safety):
    clusters = ACTION_TO_MAIN_CLUSTERS[action_id]
    base = deepcopy(patient["phase1_macros"])
    p = min(day / 30, 1.0)
    if "metabolic" in clusters: base["carbs_pct"] -= 5.0*p; base["fiber_g"] += 5.0*p
    if "lipids" in clusters: base["fat_pct"] -= 4.0*p; base["saturated_fat_pct"] -= 2.0*p; base["fiber_g"] += 3.0*p
    if "inflammation" in clusters: base["protein_g_per_kg"] += 0.05*p; base["fat_pct"] -= 1.0*p
    if "nutrition_vitamins_minerals" in clusters: base["protein_g_per_kg"] += 0.05*p
    if action_id == 0:
        base["calories_kcal"] = base.get("calories_kcal", 1750) * 0.95
        base["protein_g_per_kg"] = min(base["protein_g_per_kg"], 1.0)
    protein_cap = SURGERY_PROTEIN_CAP.get(patient["surgery_type"], 1.8)
    cap_reasons = [f"{patient['surgery_type']} surgery cap: {protein_cap} g/kg"]
    if safety["organ_function_caution"]: protein_cap = min(protein_cap, 1.2); cap_reasons.append("Organ caution: capped at 1.2 g/kg")
    if safety["high_safety_risk"]: protein_cap = min(protein_cap, 1.0); cap_reasons.append("Safety risk: capped at 1.0 g/kg")
    macro_notes = []
    for k in ["protein_g_per_kg", "carbs_pct", "fat_pct", "fiber_g", "saturated_fat_pct"]:
        lo, hi = MACRO_BOUNDS[k]
        if k == "protein_g_per_kg": hi = min(hi, protein_cap)
        base[k] = round(max(lo, min(hi, base[k])), 1)
    for k in ["protein_g_per_kg", "carbs_pct", "fat_pct", "fiber_g", "saturated_fat_pct"]:
        pv = patient["phase1_macros"].get(k)
        if pv and abs(pv) > 1e-9:
            if abs((base[k] - pv) / abs(pv)) > 0.20:
                base[k] = round(pv * (1 + (0.20 if base[k] > pv else -0.20)), 1)
                lo, hi = MACRO_BOUNDS[k]
                if k == "protein_g_per_kg": hi = min(hi, protein_cap)
                base[k] = round(max(lo, min(hi, base[k])), 1)
                macro_notes.append("Rate-of-change limit applied (≤ 20% from Phase 1)")
                break
    return base, cap_reasons, list(set(macro_notes))


def _day_hash(pid, aid, day, slot):
    return int(hashlib.md5(f"{pid}:{aid}:{day}:{slot}".encode()).hexdigest(), 16)


def collect_kg_data(action_id, doctor_targets, is_vegetarian):
    """Collect KG ingredients organized by slot category. Returns slot pools and metadata."""
    clusters = ACTION_TO_MAIN_CLUSTERS[action_id]
    # Merge all KG ingredients by slot across active clusters
    slot_pools = {"grain": [], "legume": [], "vegetable": [], "fruit": [],
                  "nut": [], "seed": [], "spice": [], "dairy": [], "protein_source": []}
    subjects = []
    ingredients_by_biomarker = {}

    source = "stabilizing" if action_id == 0 else None
    bio_sources = {}
    if action_id == 0:
        data = KG_INGREDIENTS.get("stabilizing", {}).get("_general", {})
        subjects.extend([{"subject": s, "contribution": 0.5} for s in data.get("subjects", [])])
        for slot, ings in data.get("by_slot", {}).items():
            if slot in slot_pools:
                for ing in ings:
                    if ing not in slot_pools[slot]:
                        slot_pools[slot].append(ing)
        for bio in doctor_targets:
            ingredients_by_biomarker[bio] = []
            for slot, ings in data.get("by_slot", {}).items():
                ingredients_by_biomarker[bio].extend(ings[:3])
    else:
        for c in clusters:
            for bio, bdata in KG_INGREDIENTS.get(c, {}).items():
                subjects.extend([{"subject": s, "contribution": 0.5} for s in bdata.get("subjects", [])])
                bio_ings = []
                for slot, ings in bdata.get("by_slot", {}).items():
                    if slot in slot_pools:
                        for ing in ings:
                            if ing not in slot_pools[slot]:
                                slot_pools[slot].append(ing)
                            bio_ings.append(ing)
                if bio in doctor_targets:
                    ingredients_by_biomarker[bio] = bio_ings

    # Vegetarian filter
    if is_vegetarian:
        for slot in slot_pools:
            slot_pools[slot] = [i for i in slot_pools[slot] if i.lower() not in NON_VEG_TERMS]
        for bio in ingredients_by_biomarker:
            ingredients_by_biomarker[bio] = [i for i in ingredients_by_biomarker[bio] if i.lower() not in NON_VEG_TERMS]

    # Dedup subjects
    seen = set()
    unique_subj = [s for s in subjects if not (s["subject"] in seen or seen.add(s["subject"]))]

    # Coverage
    active = [b for b in doctor_targets if BIOMARKER_TO_CLUSTER.get(b) in clusters or action_id == 0]
    covered = [b for b in active if b in ingredients_by_biomarker and ingredients_by_biomarker[b]]

    return {
        "slot_pools": slot_pools,
        "ingredients_by_biomarker": ingredients_by_biomarker,
        "subjects": unique_subj,
        "coverage_fraction": round(len(covered) / max(1, len(active)), 2),
        "active_biomarkers": active,
        "covered_biomarkers": covered,
        "missing_biomarkers": [b for b in active if b not in covered],
    }


def generate_daily_recipe(action_id, patient, day, doctor_targets, kg_data):
    """Generate 5 daily meals STRICTLY from KG ingredient pools."""
    pid = patient["patient_id"]
    pools = kg_data["slot_pools"]

    meals = []
    for slot_key, label in [("breakfast", "Breakfast"), ("mid_morning", "Mid-morning"),
                             ("lunch", "Lunch"), ("snack", "Snack"), ("dinner", "Dinner")]:
        templates = RECIPE_TEMPLATES[slot_key]
        tpl = templates[_day_hash(pid, action_id, day, f"tpl_{slot_key}") % len(templates)]
        filled_name, filled_method, used = tpl["name"], tpl["method"], []

        for cat in ["grain", "legume", "vegetable", "fruit", "nut", "seed", "spice", "dairy", "protein_source"]:
            ph = "{" + cat + "}"
            if ph in filled_name or ph in filled_method:
                pool = pools.get(cat, [])
                if pool:
                    ing = pool[_day_hash(pid, action_id, day, f"{slot_key}_{cat}") % len(pool)]
                else:
                    ing = cat  # fallback label if pool is empty
                filled_name = filled_name.replace(ph, ing)
                filled_method = filled_method.replace(ph, ing)
                used.append(ing)

        # Tag with biomarkers this meal's ingredients support
        bio_tags = []
        for bio, bio_ings in kg_data["ingredients_by_biomarker"].items():
            if any(u.lower() in [bi.lower() for bi in bio_ings] for u in used):
                d = doctor_targets.get(bio, "")
                bio_tags.append(f"{'↓' if d == 'reduce' else '↑'} {bio}")

        meals.append({"time": label, "name": filled_name.title(), "method": filled_method,
                      "ingredients": used, "tags": tpl["tags"], "biomarker_targets": bio_tags})
    return meals


def get_supplements(action_id):
    SUPPS = {"stabilizing": ["Probiotics 5B CFU", "Vitamin D3 1000 IU", "Magnesium glycinate"],
             "metabolic": ["Berberine 500mg", "Cinnamon extract", "Probiotics 5B CFU", "Vitamin D3 1000 IU"],
             "lipids": ["Omega-3 1g EPA+DHA", "Psyllium husk 5g", "Konjac glucomannan", "Plant sterols 2g"],
             "inflammation": ["Omega-3 1g EPA+DHA", "Curcumin + piperine 500mg", "Probiotics 5B CFU"],
             "nutrition_vitamins_minerals": ["Folate 400mcg", "Vitamin B12 500mcg", "Iron (if indicated)", "Vitamin D3"]}
    if action_id == 0: return SUPPS["stabilizing"]
    return sorted(set(s for c in ACTION_TO_MAIN_CLUSTERS[action_id] for s in SUPPS.get(c, [])))


def compute_conformal(action_id, doctor_targets, safety, kg_data):
    cov = kg_data["coverage_fraction"]; reasons = []
    if safety["high_safety_risk"]: reasons.append("Safety gate did not pass")
    if cov < 0.60: reasons.append(f"Weak evidence coverage ({cov:.0%})")
    if reasons: conf = "LOW"
    elif cov >= 0.80 and not safety["organ_function_caution"]: conf = "HIGH"
    else: conf = "MODERATE"; (reasons.append(f"Partial evidence coverage ({cov:.0%})") if cov < 0.80 else None)
    eff = conf
    if safety["high_safety_risk"] and conf == "HIGH": eff = "MODERATE"
    return {"confidence": conf, "effective_confidence": eff, "coverage_fraction": cov,
            "escalation_reason": "; ".join(reasons) if reasons else None}


def routing_policy(conformal, safety):
    level = conformal["effective_confidence"]
    if safety["high_safety_risk"]:
        return {"physician_review": True, "patient_plan_allowed": False, "routing": "Escalate — physician review before patient plan"}
    if level == "LOW":
        return {"physician_review": True, "patient_plan_allowed": False, "routing": "Escalate — low confidence"}
    if level == "MODERATE":
        return {"physician_review": True, "patient_plan_allowed": True, "routing": "Cautious — physician review recommended"}
    return {"physician_review": True, "patient_plan_allowed": True, "routing": "Normal — physician reviews and approves"}


def weekly_decision(current_action, intended_action, weekly_adherence, safety):
    if safety["high_safety_risk"] or weekly_adherence < 0.55:
        r = "a safety concern was detected" if safety["high_safety_risk"] else f"adherence was low this week ({weekly_adherence:.0%})"
        return {"decision": "simplified", "next_action": 0,
                "reason": f"Plan simplified — {r}. Reverting to basic recovery until resolved.",
                "badge": "🔴", "label": "Plan simplified"}
    if current_action == 0 and intended_action != 0:
        if weekly_adherence >= 0.80:
            return {"decision": "advancing", "next_action": intended_action,
                    "reason": f"Plan advancing — strong adherence ({weekly_adherence:.0%}) and safety clear. Stepping up to targeted recovery.",
                    "badge": "✅", "label": "Plan advancing"}
        return {"decision": "continues", "next_action": 0,
                "reason": f"Plan continues — adherence building ({weekly_adherence:.0%}). Continuing basic recovery.",
                "badge": "➡️", "label": "Plan continues"}
    return {"decision": "continues", "next_action": current_action,
            "reason": f"Plan continues — adherence acceptable ({weekly_adherence:.0%}) and safety clear.",
            "badge": "➡️", "label": "Plan continues"}


# ═══════════════════════════════════════════════════════════════════════════════
# STREAMLIT UI
# ═══════════════════════════════════════════════════════════════════════════════

if "daily_adherence" not in st.session_state: st.session_state.daily_adherence = {}
if "safety_override" not in st.session_state: st.session_state.safety_override = False
if "adh_profile" not in st.session_state: st.session_state.adh_profile = "well"

patient = DEMO_PATIENT
patient_id = patient["patient_id"]

st.markdown("# 🧬 30-Day Personalized Metabolic Recovery Plan")
st.caption("Post-operative metabolic recovery — AI-generated, physician-reviewed, patient-personalised.")

# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Demo Controls")

    st.subheader("Recovery plan")
    st.caption("The AI selects one of 15 targeted plans. "
               "If safety is triggered, it falls back to basic recovery automatically.")
    preset_actions = [3, 4, 9, 14]
    plan_choice = st.radio("Select plan", preset_actions + [-1],
        format_func=lambda x: PLAN_DISPLAY.get(x, "Custom — choose specific plan") if x >= 0 else "Custom — choose specific plan",
        index=2)
    if plan_choice == -1:
        intended_action = st.selectbox("Specific plan", list(range(1, 16)),
            format_func=lambda x: PLAN_DISPLAY[x], index=8)
    else:
        intended_action = plan_choice

    st.divider()
    st.subheader("Patient adherence profile")
    st.caption("One click fills all 30 days with a realistic adherence pattern.")
    profile_choice = st.radio("Adherence pattern", ["well", "moderate", "low"],
        format_func=lambda x: {"well": "🟢 Well-adhered (~85%)", "moderate": "🟡 Moderate (~55%)", "low": "🔴 Low (~25%)"}[x],
        index=["well", "moderate", "low"].index(st.session_state.adh_profile),
        key="profile_radio")
    if profile_choice != st.session_state.adh_profile or st.button("Apply profile"):
        st.session_state.adh_profile = profile_choice
        for d in range(1, 31):
            st.session_state.daily_adherence[f"adh_{patient_id}_{d}"] = ADHERENCE_PROFILES[profile_choice][d-1]
        st.rerun()

    st.divider()
    st.subheader("Patient profile")
    is_veg = st.checkbox("🌿 Vegetarian", value=patient["is_vegetarian"])
    patient["is_vegetarian"] = is_veg

    st.divider()
    st.session_state.safety_override = st.checkbox("⚠️ Simulate safety concern",
        value=st.session_state.safety_override,
        help="Simulates abnormal sodium (128.5) and INR (1.35). System falls back to basic recovery.")
    if st.button("🔄 Reset all data"):
        st.session_state.daily_adherence = {}
        st.session_state.adh_profile = "well"
        st.rerun()


# ─── Compute safety ──────────────────────────────────────────────────────────
doctor_targets = auto_doctor_targets(intended_action)
labs = deepcopy(patient["phase2_entry_labs"])
if st.session_state.safety_override:
    labs["sodium"] = 128.5; labs["INR"] = 1.35
safety = evaluate_safety(labs)
day1_action = 0 if safety["high_safety_risk"] else intended_action

# ─── 1. Patient profile ──────────────────────────────────────────────────────
st.markdown("### 👤 Patient Profile")
p = patient
parts = [f"**{p['patient_id']}** — {p['age']}-year-old {'female' if p['sex']=='F' else 'male'}, "
         f"post-**{p['surgery_type']}** surgery, BMI {p['bmi']}"]
if p['is_vegetarian']: parts.append("🌿 vegetarian")
if p['type_2_diabetes']: parts.append("type 2 diabetes")
if p['allergies']: parts.append(f"allergies: {', '.join(p['allergies'])}")
if p['medications']: parts.append(f"medications: {', '.join(p['medications'])}")
st.markdown(", ".join(parts))

# ─── 2. Doctor's goals ───────────────────────────────────────────────────────
st.markdown("---")
st.markdown("### 🎯 Doctor's Biomarker Targets")
st.caption(f"_Targeted plan: **{PLAN_DISPLAY[intended_action]}**_"
           + (" — ⚠️ _currently in safety fallback_" if safety["high_safety_risk"] else ""))

active_clusters_intended = ACTION_TO_MAIN_CLUSTERS[intended_action]
goal_cols = st.columns(len(active_clusters_intended))
for i, cluster in enumerate(active_clusters_intended):
    icon, display_name = CLUSTER_DISPLAY[cluster]
    with goal_cols[i]:
        st.markdown(f"**{icon} {display_name}**")
        for bio in MAIN_CQL_CLUSTERS[cluster]:
            if bio in doctor_targets:
                d = doctor_targets[bio]
                st.markdown(f"{'🔻' if d == 'reduce' else '🔺'} {bio} — _{d}_")

# Safety monitoring
st.markdown("**🛡️ Safety monitoring** _(always checked — not AI-targeted)_")
safety_bios = {"eGFR": (60, 999, "≥60"), "sodium": (135, 145, "135–145"), "INR": (0.8, 1.2, "0.8–1.2"),
               "free T3": (2.3, 4.2, "2.3–4.2"), "microalbumin": (0, 30, "<30")}
scols = st.columns(len(safety_bios))
for i, (bio, (lo, hi, norm)) in enumerate(safety_bios.items()):
    with scols[i]:
        val = labs.get(bio, 0); ok = lo <= val <= hi
        st.markdown(f"{'✅' if ok else '🔴'} {bio}: **{val:.1f}** _(normal: {norm})_")

# ─── 3. 30-Day Calendar ──────────────────────────────────────────────────────
st.markdown("---")
st.markdown("### 📅 30-Day Adherence Overview with Weekly Checks")

st.markdown("""
<div style="
    font-size: 0.86rem;
    padding: 0.75rem 1rem;
    border-radius: 0.6rem;
    background-color: rgba(49, 51, 63, 0.06);
    border-left: 4px solid #6c63ff;
    margin-bottom: 1rem;
">
    <strong>Weekly adherence logic [Calculated on day 7, 14, and 21]</strong>
    <table style="width:100%; margin-top:0.5rem; border-collapse: collapse;">
        <tr>
            <td style="padding:0.25rem 0;"><strong>&lt; 55%</strong></td>
            <td style="padding:0.25rem 0;">Step down to <strong>Basic Recovery</strong></td>
        </tr>
        <tr>
            <td style="padding:0.25rem 0;"><strong>55%–79%</strong></td>
            <td style="padding:0.25rem 0;">Continue the current/basic plan</td>
        </tr>
        <tr>
            <td style="padding:0.25rem 0;"><strong>≥ 80%</strong></td>
            <td style="padding:0.25rem 0;">Step up to <strong>Targeted Recovery</strong>, only if currently in Basic Recovery and safety is clear</td>
        </tr>
    </table>
    <div style="margin-top:0.4rem; color: #666;">
        Reviews are calculated at the end of each weekly checkpoint.
    </div>
</div>
""", unsafe_allow_html=True)

adh_map_val = {0: 0.80, 1: 0.40, 2: 0.05}
adh_icons = {0: "✅", 1: "🟡", 2: "🔴"}

review_log = {}
current_action = day1_action
for rd in [7, 14, 21]:
    rw = math.ceil(rd / 7); rws = (rw-1)*7+1; rwe = min(rw*7, 30)
    rscores = [adh_map_val[st.session_state.daily_adherence.get(f"adh_{patient_id}_{d}", 0)] for d in range(rws, rwe+1)]
    result = weekly_decision(current_action, intended_action, sum(rscores)/len(rscores), safety)
    review_log[rd] = result; current_action = result["next_action"]

for week_num in range(1, 6):
    ws = (week_num-1)*7+1; we = min(week_num*7, 30)
    if ws > 30: break
    cols = st.columns(we - ws + 2)
    with cols[0]: st.markdown(f"**Wk {week_num}**")
    for i, d in enumerate(range(ws, we+1)):
        with cols[i+1]:
            idx = st.session_state.daily_adherence.get(f"adh_{patient_id}_{d}", 0)
            st.markdown(f"{adh_icons[idx]} D{d}")
    rd = we if we in review_log else None
    if rd:
        r = review_log[rd]
        st.caption(f"  Day {rd} review: {r['badge']} {r['label']} — {r['reason']}")

# ─── 4. Day selector ─────────────────────────────────────────────────────────
st.markdown("---")
day = st.selectbox("📅 Select a day to view its recommendation", list(range(1, 31)),
                   format_func=lambda d: f"Day {d}  (Week {math.ceil(d/7)})")

active_action = day1_action
for rd in [7, 14, 21]:
    if rd <= day and rd in review_log:
        active_action = review_log[rd]["next_action"]

# ─── 5. Plan status + safety ─────────────────────────────────────────────────
st.markdown("---")

if safety["high_safety_risk"]:
    st.error(f"""
**⚠️ SAFETY ALERT**

{' '.join([r for r in safety['reasons'] if 'All safety' not in r])}

**What the system did:**
- Plan automatically fell back to basic recovery nutrition
- Protein capped at {min(1.0, SURGERY_PROTEIN_CAP.get(patient['surgery_type'], 1.8)):.1f} g/kg (safety override)
- Patient-facing meal plan withheld pending physician review
- **Physician escalation: REQUIRED** before resuming targeted plan

_This is a hard safety rule — it cannot be overridden by the AI.
When safety clears, the plan resumes at the next weekly review._
    """)

if safety["high_safety_risk"]:
    st.warning(f"**🏥 Safety fallback active** — intended plan: _{PLAN_DISPLAY[intended_action]}_. "
               f"Will step up when safety clears and adherence ≥ 80%.")
elif active_action == 0 and intended_action != 0:
    st.info(f"**🏥 Safety fallback active** — adherence low or recent safety concern. "
            f"Intended: _{PLAN_DISPLAY[intended_action]}_. Will step up when adherence ≥ 80%.")
elif active_action == intended_action:
    st.success(f"**✅ Targeted plan active** — {PLAN_DISPLAY[active_action]}")

passed = [(rd, r) for rd, r in review_log.items() if rd <= day]
if passed:
    lat_day, lat = passed[-1]
    st.markdown(f"> {lat['badge']} **Day {lat_day} review:** {lat['reason']}")

# ─── 6. Active categories ────────────────────────────────────────────────────
st.markdown("---")
st.markdown(f"### 📋 Active Recovery Categories — Day {day}")

active_clusters_now = ACTION_TO_MAIN_CLUSTERS[active_action]
if active_action == 0:
    st.markdown(f"_⚠️ Safety fallback — gentle recovery nutrition and monitoring. "
                f"When resolved, plan steps up to **{PLAN_DISPLAY[intended_action]}** "
                f"targeting: {', '.join([CLUSTER_DISPLAY[c][1] for c in ACTION_TO_MAIN_CLUSTERS[intended_action]])}._")
else:
    cat_cols = st.columns(len(active_clusters_now))
    for i, cluster in enumerate(active_clusters_now):
        icon, display_name = CLUSTER_DISPLAY[cluster]
        with cat_cols[i]:
            st.markdown(f"#### {icon} {display_name}")
            for bio in MAIN_CQL_CLUSTERS[cluster]:
                if bio in doctor_targets:
                    st.markdown(f"{'🔻' if doctor_targets[bio]=='reduce' else '🔺'} {bio}")

# ─── 7. Macro targets ────────────────────────────────────────────────────────
kg_data = collect_kg_data(active_action, doctor_targets, patient["is_vegetarian"])
macros, cap_reasons, macro_notes = expand_macros(active_action, patient, day, safety)

st.markdown("---")
st.markdown(f"### 📊 Macro Targets — Day {day}")

mc = st.columns(5)
mlabels = {"protein_g_per_kg": ("Protein", "g/kg"), "carbs_pct": ("Carbs", "% kcal"),
           "fat_pct": ("Fat", "% kcal"), "fiber_g": ("Fibre", "g/day"), "saturated_fat_pct": ("Sat. fat", "% kcal")}
for i, (k, (lbl, unit)) in enumerate(mlabels.items()):
    with mc[i]:
        delta = round(macros[k] - patient["phase1_macros"].get(k, macros[k]), 1)
        st.metric(f"{lbl} ({unit})", f"{macros[k]}", delta=f"{delta:+.1f} vs Phase 1")

rule_notes = list(cap_reasons[:1]) + ["Rate of change ≤ 20% from Phase 1"] + macro_notes
st.caption("**Physician rules applied:** " + " · ".join(rule_notes))

# ─── 8. Key evidence ingredients ──────────────────────────────────────────────
st.markdown("---")
st.markdown("### 🧪 Key Evidence Ingredients")
st.caption("_All daily recipes (Day 1–30) are built strictly from these KG-backed (Nutrition Vs. Biomarker Dataset) ingredients. "
           "Each ingredient is linked to a specific biomarker target through published evidence._")

if active_action == 0:
    st.markdown("_Safety fallback — gentle recovery ingredients:_")
    for slot, ings in kg_data["slot_pools"].items():
        if ings:
            st.markdown(f"**{slot.replace('_', ' ').title()}:** {', '.join(ings)}")
else:
    active_clusters_now = ACTION_TO_MAIN_CLUSTERS[active_action]
    for cluster in active_clusters_now:
        icon, display_name = CLUSTER_DISPLAY[cluster]
        bios_in_cluster = [b for b in doctor_targets if BIOMARKER_TO_CLUSTER.get(b) == cluster]
        if bios_in_cluster:
            st.markdown(f"**{icon} {display_name}**")
            for bio in bios_in_cluster:
                d = doctor_targets[bio]
                arrow = "🔻" if d == "reduce" else "🔺"
                # Collect ingredients for this biomarker from KG, organized by slot
                bio_data = {}
                for c_name in [cluster]:
                    for bio_key, bdata in KG_INGREDIENTS.get(c_name, {}).items():
                        if bio_key == bio:
                            for slot, ings in bdata.get("by_slot", {}).items():
                                filtered = ings if not patient["is_vegetarian"] else [i for i in ings if i.lower() not in NON_VEG_TERMS]
                                if filtered:
                                    bio_data[slot] = filtered
                if bio_data:
                    all_ings = []
                    for slot_ings in bio_data.values():
                        all_ings.extend(slot_ings)
                    # Deduplicate while preserving order
                    seen = set()
                    unique_ings = [i for i in all_ings if not (i in seen or seen.add(i))]
                    st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;{arrow} **{bio}** → {', '.join(unique_ings)}")

    st.caption(f"Evidence coverage: **{kg_data['coverage_fraction']:.0%}** of targeted biomarkers covered by KG ingredients.")

# ─── 9. Daily meals (STRICTLY from KG ingredients) ───────────────────────────
daily_meals = generate_daily_recipe(active_action, patient, day, doctor_targets, kg_data)

st.markdown("---")
st.markdown(f"### 🍽️ Today's Meals — Day {day}")
st.caption(f"_Every ingredient below is drawn from the evidence pool above.")

for meal in daily_meals:
    with st.expander(f"**{meal['time']}** — {meal['name']}", expanded=(meal['time'] in ['Breakfast', 'Lunch', 'Dinner'])):
        col_r1, col_r2 = st.columns([3, 1])
        with col_r1:
            st.markdown(f"**How to prepare:** {meal['method']}")
            st.markdown(f"**Ingredients:** {', '.join(meal['ingredients'])}")
        with col_r2:
            if meal["biomarker_targets"]:
                st.markdown("**Supports:**")
                for bt in meal["biomarker_targets"]:
                    st.markdown(f"&nbsp;&nbsp;🎯 {bt}")
            st.markdown(" · ".join([f"`{t}`" for t in meal["tags"]]))

# ─── 10. Supplements ─────────────────────────────────────────────────────────
supps = get_supplements(active_action)
st.markdown("---")
st.markdown("### 💊 Supplements & Functional Foods")
st.markdown(" · ".join([f"💊 {s}" for s in supps]))

# ─── 11. Safety status + confidence ──────────────────────────────────────────
st.markdown("---")
st.markdown("### 🛡️ Safety Status")
if not safety["high_safety_risk"] and not safety["organ_function_caution"]:
    st.success("✅ All safety checks passed. No restrictions applied.")
else:
    for reason in safety["reasons"]:
        if "All safety" not in reason: st.warning(reason)

conformal = compute_conformal(active_action, doctor_targets, safety, kg_data)
routing = routing_policy(conformal, safety)
conf_icon = {"HIGH": "🟢", "MODERATE": "🟡", "LOW": "🔴"}.get(conformal["effective_confidence"], "⚪")
st.markdown(f"**System confidence:** {conf_icon} {conformal['effective_confidence']} · **Routing:** {routing['routing']}")
st.markdown(f"**Physician review required:** {'Yes' if routing['physician_review'] else 'No'} · "
            f"**Patient-facing plan:** {'Yes ✅' if routing['patient_plan_allowed'] else 'No ❌'}")

# ─── 12. Technical details ────────────────────────────────────────────────────
with st.expander("🔧 Technical Details (for development team)"):
    st.markdown(f"""
**CQL action ID:** {active_action} — `{DISCRETE_ACTION_SPACE[active_action]}`
**CQL intended:** {intended_action} — `{DISCRETE_ACTION_SPACE[intended_action]}`
**Day 1 action:** {day1_action} {'(⚠️ safety fallback)' if day1_action == 0 and intended_action != 0 else '(direct start)'}
**Active clusters:** {ACTION_TO_MAIN_CLUSTERS[active_action] or 'None (safety fallback)'}
**Intended clusters:** {ACTION_TO_MAIN_CLUSTERS[intended_action]}
**KG subjects:** {len(kg_data['subjects'])}
**KG coverage:** {kg_data['coverage_fraction']:.0%}
**Conformal confidence:** {conformal['confidence']} (effective: {conformal['effective_confidence']})
**Escalation reason:** {conformal['escalation_reason'] or 'None'}
    """)
    st.markdown("**KG Subject Details:**")
    for s in kg_data["subjects"][:10]:
        st.markdown(f"- {s['subject']} (contribution: {s['contribution']:.2f})")
    st.markdown("**KG Slot Pools (what recipes draw from):**")
    for slot, ings in kg_data["slot_pools"].items():
        if ings:
            st.markdown(f"- **{slot}:** {', '.join(ings)}")

st.markdown("---")
st.caption("**Architecture:** Bayesian Clinical Network → Dynamic Treatment Regime → Conservative Q-Learning (Day 1/30/60/90) "
           "→ Weekly Adherence Review (Day 7/14/21) → Conformal Prediction → Hard Safety Gate → Physician Review → Patient Plan. "
           "Biomarker outcomes measured at Day 30 lab checkpoint.")
