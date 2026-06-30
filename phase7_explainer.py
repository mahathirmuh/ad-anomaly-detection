#!/usr/bin/env python3
"""
Phase 7 — Anomaly Explainer (Proof of Concept)
================================================
Mengubah output anomali (skor + top fitur SHAP) menjadi penjelasan yang
DAPAT DIBACA MANUSIA, di-grounding ke knowledge base keamanan.

Dua tier:
  - Penjelasan Ringkas (template) : berbasis KB. Deterministik, tanpa LLM, nol halusinasi. [offline]
  - Penjelasan Naratif (AI)        : LLM OpenAI menyusun narasi natural dari KB. [butuh OPENAI_API_KEY]
                        Butuh `pip install openai python-dotenv` + OPENAI_API_KEY di .env

LLM HANYA merangkai fakta + entri KB yang diberikan — tidak mengarang.
Sumber: knowledge_base/security_kb.yaml (MITRE terverifikasi + Event ID + threshold dari kode).
"""

import os
import json
import yaml
import pandas as pd

KB_PATH = "knowledge_base/security_kb.yaml"
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")  # override via .env bila perlu


# --------------------------------------------------------------------------- #
# .env loader (python-dotenv bila ada; fallback parser sederhana)
# --------------------------------------------------------------------------- #
def load_env(path=".env"):
    try:
        from dotenv import load_dotenv
        load_dotenv(path)
        return
    except ImportError:
        pass
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


# --------------------------------------------------------------------------- #
# Load data
# --------------------------------------------------------------------------- #
_KB = {}  # diisi oleh load_kb() — untuk akses severity / mitigasi / pola_kombinasi

def load_kb():
    global _KB
    with open(KB_PATH, encoding="utf-8") as f:
        kb = yaml.safe_load(f)
    _KB = kb
    rules = {r["id"]: r for r in kb["rules"]}
    feats = {f["id"]: f for f in kb["features"]}
    return kb, rules, feats


def load_anomalies(top_n=5):
    shap = pd.read_csv("data/phase55_shap_anomalies.csv")
    feat = pd.read_csv("data/phase4_graph_features.csv")
    df = (shap.sort_values("anomaly_score", ascending=False)
              .drop_duplicates("user_id")
              .head(top_n))
    df = df.merge(feat, on="user_id", how="left", suffixes=("", "_feat"))
    return df


# --------------------------------------------------------------------------- #
# Bangun konteks ter-grounding dari KB
# --------------------------------------------------------------------------- #
def build_context(row, feats, rules):
    top = [row.get("top_feature_1"), row.get("top_feature_2"), row.get("top_feature_3")]
    top = [t for t in top if isinstance(t, str) and t]

    kb_entries, seen_rules, techniques, rules_involved = [], set(), [], []
    for fid in top:
        fe = feats.get(fid)
        if not fe:
            continue
        kb_entries.append(fe)
        rid = fe.get("rule_terkait")
        if rid and rid in rules and rid not in seen_rules:
            r = rules[rid]; kb_entries.append(r); seen_rules.add(rid); rules_involved.append(r)
            for m in r.get("mitre", []):
                tid = m.split()[0]
                if tid not in techniques:
                    techniques.append(tid)

    facts = {fid: row[fid] for fid in top if fid in row and pd.notna(row.get(fid))}

    # --- pengayaan dari KB: severity, mitigasi MITRE, pola kombinasi ---
    sev = row.get("severity")
    sev_info = next((s for s in _KB.get("severity", {}).get("level", []) if s.get("nama") == sev), None)
    ref = _KB.get("meta", {}).get("referensi_resmi", {})
    mit_map = ref.get("mitre_mitigations", {})
    mitigasi = []
    for tid in techniques:
        for key in (tid, tid.split(".")[0]):   # T1078.002 -> fallback T1078
            if key in mit_map:
                mitigasi = mit_map[key]; break
        if mitigasi:
            break
    topset = set(top)
    kombinasi = next((k for k in _KB.get("pola_kombinasi", [])
                      if set(k.get("kombinasi", [])).issubset(topset)), None)

    # --- source links: URL EKSAK dari KB (bukan digenerate LLM) ---
    mitre_ref = {m["id"]: m for m in ref.get("mitre_attack", [])}
    ev_ref = ref.get("windows_event_id", [])
    sumber_links, seen_url = [], set()
    for r in rules_involved:
        for m in r.get("mitre", []):
            tid = m.split()[0]
            ent = mitre_ref.get(tid) or mitre_ref.get(tid.split(".")[0])
            if ent and ent["url"] not in seen_url:
                seen_url.add(ent["url"]); sumber_links.append((ent["id"], ent["url"]))
        ev_text = r.get("event_id", "")
        for e in ev_ref:
            nums = [n for n in e["id"].replace("/", " ").split() if n.isdigit()]
            if any(n in ev_text for n in nums) and e["url"] not in seen_url:
                seen_url.add(e["url"]); sumber_links.append((f"Event {e['id']}", e["url"]))

    extra = {"severity": sev_info, "mitigasi": mitigasi, "kombinasi": kombinasi,
             "sumber_links": sumber_links}
    return top, kb_entries, facts, extra


# --------------------------------------------------------------------------- #
# Penjelasan Ringkas (template) — offline, tanpa LLM
# --------------------------------------------------------------------------- #
def explain_tier1(row, feats, rules):
    top, _, facts, extra = build_context(row, feats, rules)
    user = row.get("username") or row.get("user_id")
    sev = row.get("severity", "?")
    score = row.get("anomaly_score", float("nan"))

    lines = [f"**{user}** — severity {sev}, skor {float(score):.3f}"]
    if extra["severity"]:
        lines.append(f"- Severity {sev}: {extra['severity'].get('ambang')} ({extra['severity'].get('arti')})")
    f1 = top[0] if top else None
    rule = {}
    if f1 and f1 in feats:
        fe = feats[f1]
        rule = rules.get(fe.get("rule_terkait"), {})
        val = facts.get(f1)
        val_s = f" = {val}" if val is not None else ""
        lines.append(f"- Penyebab utama: **{fe['label']}** (`{f1}`{val_s})")
        if rule:
            lines.append(f"  - Mengapa berbahaya: {rule.get('kenapa_bahaya', '-')}")
            lines.append(f"  - MITRE: {', '.join(rule.get('mitre', [])) or '-'}")
            lines.append(f"  - Event ID: {rule.get('event_id', '-')}")
            lines.append(f"  - Rekomendasi: {rule.get('rekomendasi', '-')}")
    if extra["mitigasi"]:
        lines.append(f"- Mitigasi MITRE: {', '.join(extra['mitigasi'])}")
    if extra["kombinasi"]:
        lines.append(f"- Pola kombinasi: {extra['kombinasi'].get('makna')}")
    if rule:
        lines.append(f"- Sumber: {rule.get('sumber', '-')}")
    if extra["sumber_links"]:
        lines.append("- Sumber (link): " + " · ".join(f"[{lbl}]({url})" for lbl, url in extra["sumber_links"]))
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Penjelasan Naratif (AI) — OpenAI, grounded ke KB
# --------------------------------------------------------------------------- #
SYSTEM_PROMPT = (
    "Anda analis keamanan Active Directory. Tulis penjelasan anomali dalam Bahasa "
    "Indonesia yang ringkas, KONSISTEN, dan dapat dibaca manusia.\n"
    "ATURAN KETAT (grounding & konsistensi):\n"
    "- HANYA gunakan fakta pada BUKTI dan pengetahuan pada KNOWLEDGE BASE yang diberikan.\n"
    "- JANGAN mengarang angka, teknik MITRE, Event ID, atau sebab di luar yang disediakan.\n"
    "- Setia pada bukti: gunakan nilai faktual apa adanya (mis. lockout_count=12693).\n"
    "- ISTILAH `failure_ratio`: DILARANG menyebutnya 'rasio' atau 'proporsi'. Nilainya BUKAN "
    "0-1 (bisa puluhan ribu). Sebut sebagai 'intensitas login gagal' atau 'jumlah login gagal "
    "per relasi login'. Boleh sertakan angkanya, tapi jangan diframing sebagai persentase/proporsi.\n"
    "- Selalu cantumkan sumber (MITRE ID/URL, Event ID) dari knowledge base.\n"
    "- Jika informasi kurang untuk suatu klaim, nyatakan demikian — jangan menebak.\n"
    "- Pakai STRUKTUR & GAYA yang SAMA untuk SETIAP anomali (template seragam); "
    "hanya isi yang berbeda. Setiap field selalu terisi, urutan tetap.\n\n"
    "Field output:\n"
    "  ringkasan   — 1-2 kalimat: username, severity, skor, penyebab utama.\n"
    "  penjelasan  — kenapa pola mencurigakan + kaitan rule + teknik MITRE.\n"
    "  bukti       — nilai faktual (fitur=nilai, rule terkait).\n"
    "  rekomendasi — langkah konkret untuk analis.\n"
    "  sumber      — daftar MITRE ID/URL & Event ID yang dirujuk."
)

# Skema KETAT — menjamin template seragam untuk SEMUA anomali (OpenAI structured outputs).
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "ringkasan": {"type": "string"},
        "penjelasan": {"type": "string"},
        "bukti": {"type": "string"},
        "rekomendasi": {"type": "string"},
        "sumber": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["ringkasan", "penjelasan", "bukti", "rekomendasi", "sumber"],
    "additionalProperties": False,
}


def explain_tier2(row, feats, rules, client):
    top, kb_entries, facts, extra = build_context(row, feats, rules)
    facts_json = json.dumps({
        "username": row.get("username"),
        "severity": row.get("severity"),
        "severity_info": extra["severity"],
        "anomaly_score": float(row.get("anomaly_score", 0)),
        "top_features": top,
        "feature_values": {k: (float(v) if hasattr(v, "__float__") else v)
                           for k, v in facts.items()},
        "mitigasi_mitre": extra["mitigasi"],
        "pola_kombinasi": (extra["kombinasi"] or {}).get("makna"),
        "sumber_link": [f"{lbl} — {url}" for lbl, url in extra["sumber_links"]],
    }, ensure_ascii=False, indent=2)
    kb_yaml = yaml.safe_dump(kb_entries, allow_unicode=True, sort_keys=False)

    user_msg = (
        f"BUKTI ANOMALI (faktual, jangan diubah):\n{facts_json}\n\n"
        f"KNOWLEDGE BASE (satu-satunya sumber konteks & sitasi yang boleh dipakai):\n{kb_yaml}\n\n"
        "Susun penjelasan sesuai format JSON yang diminta."
    )

    base = dict(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.2,
        max_tokens=1200,
    )
    # Structured output skema KETAT → template seragam untuk semua anomali.
    try:
        resp = client.chat.completions.create(**base, response_format={
            "type": "json_schema",
            "json_schema": {"name": "anomaly_explanation", "strict": True, "schema": OUTPUT_SCHEMA},
        })
    except Exception:  # fallback untuk model yang belum dukung json_schema
        resp = client.chat.completions.create(**base, response_format={"type": "json_object"})
    result = json.loads(resp.choices[0].message.content)
    # Sumber = URL EKSAK dari KB (override output LLM) demi kredibilitas — bukan URL karangan model.
    if extra["sumber_links"]:
        result["sumber"] = [f"[{lbl}]({url})" for lbl, url in extra["sumber_links"]]
    return result


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main():
    load_env()
    kb, rules, feats = load_kb()
    df = load_anomalies(top_n=5)

    client, use_llm = None, False
    try:
        from openai import OpenAI
        if os.getenv("OPENAI_API_KEY"):
            client = OpenAI()  # membaca OPENAI_API_KEY dari environment (.env)
            use_llm = True
    except ImportError:
        pass

    print("=" * 70)
    print("PHASE 7 — ANOMALY EXPLAINER (PoC)")
    status = f"AKTIF (model: {OPENAI_MODEL})" if use_llm \
        else "NONAKTIF — set OPENAI_API_KEY di .env + `pip install openai python-dotenv`"
    print(f"KB: {len(rules)} rule, {len(feats)} fitur  |  Penjelasan Naratif (AI): {status}")
    print("=" * 70)

    results = []
    for _, row in df.iterrows():
        print("\n" + "-" * 70)
        t1 = explain_tier1(row, feats, rules)
        print("PENJELASAN RINGKAS (template):\n" + t1)
        rec = {"user": row.get("username"), "severity": row.get("severity"), "tier1": t1}

        if use_llm:
            try:
                t2 = explain_tier2(row, feats, rules, client)
                print("\nPENJELASAN NARATIF (AI):")
                print(f"  Ringkasan  : {t2.get('ringkasan')}")
                print(f"  Rekomendasi: {t2.get('rekomendasi')}")
                src = t2.get("sumber", [])
                print(f"  Sumber     : {', '.join(src) if isinstance(src, list) else src}")
                rec["tier2"] = t2
            except Exception as e:
                print(f"\n[Penjelasan Naratif (AI) gagal: {e}]")
                rec["tier2_error"] = str(e)

        results.append(rec)

    os.makedirs("output", exist_ok=True)
    out_path = "output/phase7_explanations.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    print("\n" + "=" * 70)
    print(f"[OK] {len(results)} penjelasan tersimpan: {out_path}")


if __name__ == "__main__":
    main()
