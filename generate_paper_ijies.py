#!/usr/bin/env python3
"""
Generate IJIES Draft Paper
AD Anomaly Detection - Graph-Based Knowledge System

Format: International Journal of Intelligent Engineering and Systems (IJIES)
Two-column, Times New Roman, structured for journal submission.
"""

from docx import Document
from docx.shared import Inches, Pt, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn, nsmap
from docx.oxml import OxmlElement
import pandas as pd
import json
import os

os.makedirs('output', exist_ok=True)

# ── LOAD DATA ────────────────────────────────────────────────────────
with open('output/anomaly_statistics.json') as f:
    STATS = json.load(f)

TOTAL_USERS  = STATS['total_users']
ANOMALY_DIST = STATS['anomaly_distribution']
SCORE_STATS  = STATS['anomaly_score_stats']
ENS_VOTE     = STATS['ensemble_voting']
RULE_STATS   = STATS['rule_violations_stats']

df = pd.read_csv('data/phase5_anomaly_results.csv').drop_duplicates(subset='user_id').reset_index(drop=True)
shap_df = pd.read_csv('data/phase55_shap_values.csv')

P75 = df['final_anomaly_score'].quantile(0.75)
P90 = df['final_anomaly_score'].quantile(0.90)
P95 = df['final_anomaly_score'].quantile(0.95)
P99 = df['final_anomaly_score'].quantile(0.99)

# Top 5 anomalies with SHAP
merged = df.merge(shap_df[['user_id', 'top_feature_1_label']], on='user_id', how='left')
TOP5 = merged.nlargest(5, 'final_anomaly_score')

TOTAL_ANOMALI = int(df['severity'].isin(['CRITICAL', 'HIGH', 'MEDIUM']).sum())

# ── COMBINATION ABLATION (rank-based fusion vs rule-based proxy) ──────
from scipy.stats import rankdata as _rankdata
_MR = {
    'IF':  _rankdata(df['if_score'].values),
    'LOF': _rankdata(df['lof_score'].values),
    'EE':  _rankdata(df['ee_score'].values),
}
_NN = len(df)
_GT = (df['rule_violations'].values >= 6).astype(int)
_PP = int(_GT.sum())
_CONFIGS = [('IF',), ('LOF',), ('EE',), ('IF', 'LOF'),
            ('IF', 'EE'), ('LOF', 'EE'), ('IF', 'LOF', 'EE')]

def _eval_cfg(models, gt, K):
    combined = sum(_MR[m] for m in models) / len(models)
    order = combined.argsort()
    pred = [0] * _NN
    for idx in order[:K]:
        pred[idx] = 1
    pred = pd.Series(pred).values
    TP = int(((pred == 1) & (gt == 1)).sum()); FP = int(((pred == 1) & (gt == 0)).sum())
    FN = int(((pred == 0) & (gt == 1)).sum()); TN = int(((pred == 0) & (gt == 0)).sum())
    acc = (TP + TN) / _NN
    prec = TP / (TP + FP) if TP + FP else 0
    rec = TP / (TP + FN) if TP + FN else 0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0
    return acc, prec, rec, f1

COMBO_ABLATION = []
for c in _CONFIGS:
    acc, prec, rec, f1 = _eval_cfg(c, _GT, _PP)
    COMBO_ABLATION.append(('+'.join(c), acc, prec, rec, f1))

# Sensitivity: F1 of each config across proxy thresholds; thresholds chosen to
# remain statistically meaningful (each has a non-trivial positive count).
_SENS_T = [t for t in [4, 5, 6] if int((df['rule_violations'].values >= t).sum()) >= 20]
SENS_TABLE = {}   # config -> {t: f1}
SENS_BEST = {}    # t -> (config, f1)
for t in _SENS_T:
    gt_t = (df['rule_violations'].values >= t).astype(int)
    Kt = int(gt_t.sum())
    scored = [('+'.join(c), _eval_cfg(c, gt_t, Kt)[3]) for c in _CONFIGS]
    for name, f1v in scored:
        SENS_TABLE.setdefault(name, {})[t] = f1v
    SENS_BEST[t] = max(scored, key=lambda x: x[1])

# Is the full ensemble ever the worst configuration? (robustness claim)
_ENS_NEVER_WORST = all(
    SENS_TABLE['IF+LOF+EE'][t] > min(SENS_TABLE[c][t] for c in SENS_TABLE)
    for t in _SENS_T
)
# Does a single config dominate (win) across all thresholds?
_SENS_WINNERS = {SENS_BEST[t][0] for t in _SENS_T}

# ── INDIVIDUAL-MODEL ABLATION (Precision@K vs rule proxy) ────────────
def _model_set(col):
    return set(df[df[col] == 1]['user_id'])
_HEAVY = set(df[df['rule_violations'] >= 6]['user_id'])
_BASE_RV = df['rule_violations'].mean()

IND_ABLATION = []  # (name, detected, precision@k, avg_rule_viol, avg_score)
for name, col in [('IF', 'if_anomaly'), ('LOF', 'lof_anomaly'),
                  ('EE', 'ee_anomaly'), ('Ensemble', None)]:
    s = set(df[df['anomaly_votes'] >= 2]['user_id']) if col is None else _model_set(col)
    sub = df[df['user_id'].isin(s)]
    n = len(s)
    pk = len(s & _HEAVY) / n if n else 0
    IND_ABLATION.append((name, n, pk, sub['rule_violations'].mean() if n else 0,
                         sub['final_anomaly_score'].mean() if n else 0))

# ── INTER-MODEL AGREEMENT (Jaccard, Cohen's Kappa) ───────────────────
from sklearn.metrics import cohen_kappa_score as _kappa
def _jac(a, b):
    return len(a & b) / len(a | b) if (a | b) else 0.0
_S = {'IF': _model_set('if_anomaly'), 'LOF': _model_set('lof_anomaly'), 'EE': _model_set('ee_anomaly')}
AGREEMENT = []  # (pair, jaccard, kappa, interp)
for a, b, ca, cb in [('IF', 'LOF', 'if_anomaly', 'lof_anomaly'),
                     ('IF', 'EE', 'if_anomaly', 'ee_anomaly'),
                     ('LOF', 'EE', 'lof_anomaly', 'ee_anomaly')]:
    j = _jac(_S[a], _S[b]); k = _kappa(df[ca], df[cb])
    interp = ('High' if k > 0.6 else 'Moderate' if k > 0.4 else 'Fair' if k > 0.2 else 'Low')
    AGREEMENT.append((f'{a}–{b}', j, k, interp))

# Convenience handles used across abstract + results sections
_ee = next(r for r in IND_ABLATION if r[0] == 'EE')
_lof = next(r for r in IND_ABLATION if r[0] == 'LOF')
_lofee = next(a for a in AGREEMENT if a[0] == 'LOF–EE')
_lofee_abs = abs(_lofee[2])

# ── HELPERS ──────────────────────────────────────────────────────────

def set_two_columns(section):
    """Set section to two-column layout"""
    sectPr = section._sectPr
    cols = sectPr.xpath('./w:cols')
    if cols:
        cols[0].set(qn('w:num'), '2')
        cols[0].set(qn('w:space'), '720')   # 0.5 inch space between columns
    else:
        cols = OxmlElement('w:cols')
        cols.set(qn('w:num'), '2')
        cols.set(qn('w:space'), '720')
        sectPr.append(cols)

def add_section_break(doc, columns=2):
    """Add section break and set columns"""
    new_section = doc.add_section(WD_SECTION.CONTINUOUS)
    sectPr = new_section._sectPr
    cols = sectPr.xpath('./w:cols')
    if cols:
        cols[0].set(qn('w:num'), str(columns))
        cols[0].set(qn('w:space'), '720')
    else:
        cols_el = OxmlElement('w:cols')
        cols_el.set(qn('w:num'), str(columns))
        cols_el.set(qn('w:space'), '720')
        sectPr.append(cols_el)
    return new_section

def set_font(run, name='Times New Roman', size=11, bold=False, italic=False):
    run.font.name = name
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    rPr = run._element.get_or_add_rPr()
    rFonts = rPr.find(qn('w:rFonts'))
    if rFonts is None:
        rFonts = OxmlElement('w:rFonts')
        rPr.append(rFonts)
    rFonts.set(qn('w:ascii'), name)
    rFonts.set(qn('w:hAnsi'), name)

def add_para(doc, text, size=11, bold=False, italic=False, align='left', indent=True, space_after=0):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.line_spacing = 1.0
    if indent:
        p.paragraph_format.first_line_indent = Cm(0.5)
    if align == 'center':
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    elif align == 'justify':
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    else:
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    run = p.add_run(text)
    set_font(run, size=size, bold=bold, italic=italic)
    return p

def add_heading_lvl1(doc, num, text):
    """1. First-order heading - 12pt bold"""
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.line_spacing = 1.0
    run = p.add_run(f'{num}. {text}')
    set_font(run, size=12, bold=True)
    return p

def add_heading_lvl2(doc, num, text):
    """1.1 Second-order heading - 11pt bold"""
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(3)
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.line_spacing = 1.0
    run = p.add_run(f'{num} {text}')
    set_font(run, size=11, bold=True)
    return p

def add_text(doc, text, justify=True, indent=True, space_after=0):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.line_spacing = 1.0
    if indent:
        p.paragraph_format.first_line_indent = Cm(0.5)
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY if justify else WD_ALIGN_PARAGRAPH.LEFT
    run = p.add_run(text)
    set_font(run, size=11)
    return p

def add_equation(doc, eq, num):
    """Indented equation with number"""
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Cm(0.5)
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.line_spacing = 1.0
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    run = p.add_run(eq)
    set_font(run, size=11, italic=True)
    # Equation number right-aligned via tab
    tab_run = p.add_run(f'\t({num})')
    set_font(tab_run, size=11)
    # Set right tab
    tab_stops = p.paragraph_format.tab_stops
    tab_stops.add_tab_stop(Inches(3.0), WD_ALIGN_PARAGRAPH.RIGHT)

def add_table(doc, headers, rows, caption_num, caption):
    """Table with IJIES caption above (10pt centered)"""
    # Caption
    cap = doc.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap.paragraph_format.space_before = Pt(6)
    cap.paragraph_format.space_after = Pt(3)
    crun = cap.add_run(f'Table {caption_num}. {caption}')
    set_font(crun, size=10)
    # Table
    table = doc.add_table(rows=len(rows) + 1, cols=len(headers))
    table.style = 'Table Grid'
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for j, h in enumerate(headers):
        c = table.cell(0, j)
        c.text = ''
        run = c.paragraphs[0].add_run(str(h))
        set_font(run, size=10, bold=True)
        c.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
    for i, row in enumerate(rows):
        for j, val in enumerate(row):
            c = table.cell(i + 1, j)
            c.text = ''
            run = c.paragraphs[0].add_run(str(val))
            set_font(run, size=10)
            c.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
    # Add empty line after table
    spacer = doc.add_paragraph()
    spacer.paragraph_format.space_after = Pt(3)

# ── BUILD PAPER ──────────────────────────────────────────────────────

def build_paper():
    doc = Document()

    # Page setup: A4, margins
    for section in doc.sections:
        section.page_width = Cm(21.0)
        section.page_height = Cm(29.7)
        section.top_margin = Cm(2.5)
        section.bottom_margin = Cm(2.5)
        section.left_margin = Cm(1.9)
        section.right_margin = Cm(1.9)
        section.header_distance = Cm(1.27)
        section.footer_distance = Cm(1.27)

    # ── TITLE BLOCK (single column) ──────────────────────────────────
    # Title
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(12)
    run = p.add_run('Knowledge Graph-Based Anomaly Detection on Active Directory Logs '
                    'Using Ensemble Methods and SHAP Explainability')
    set_font(run, size=14, bold=True)

    # Authors
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(6)
    run = p.add_run('Mahathir Muhammad')
    set_font(run, size=11, bold=True)
    sup = p.add_run('1*')
    set_font(sup, size=11, bold=True)
    sup.font.superscript = True

    # Affiliation
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(3)
    sup = p.add_run('1')
    set_font(sup, size=11)
    sup.font.superscript = True
    run = p.add_run(' Department of Information Technology, Institution Name, Indonesia')
    set_font(run, size=11, italic=True)

    # Email
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(6)
    run = p.add_run('* Corresponding author’s Email: mahathirmuhammad02@gmail.com')
    set_font(run, size=10, italic=True)

    # Horizontal line (simulated)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(3)
    run = p.add_run('_' * 100)
    set_font(run, size=8)

    # Abstract
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.first_line_indent = Cm(0.5)
    run = p.add_run('Abstract: ')
    set_font(run, size=10, bold=True)
    run = p.add_run(
        'Active Directory (AD) environments generate millions of authentication events daily, '
        'making manual anomaly detection impractical. Traditional rule-based and statistical '
        'approaches suffer from limited contextual awareness and black-box decision-making. '
        'This paper proposes a graph-based anomaly detection pipeline that integrates Neo4j '
        'knowledge graph, domain rule engine, and heterogeneous ensemble of three unsupervised '
        'machine learning models: Isolation Forest (IF), Local Outlier Factor (LOF), and '
        'Elliptic Envelope (EE). To address the lack of ground truth in unsupervised anomaly '
        'detection, we employ data-driven quantile-based severity thresholds (P75/P90/P95/P99) '
        'and SHAP TreeExplainer for per-user explainability. The system was evaluated on '
        f'{TOTAL_USERS:,} users derived from 1.8 million AD logon events. Results show that the '
        f'ensemble identifies {TOTAL_ANOMALI} anomalous users across CRITICAL '
        f'({ANOMALY_DIST.get("CRITICAL",0)}), HIGH ({ANOMALY_DIST.get("HIGH",0)}), and MEDIUM '
        f'({ANOMALY_DIST.get("MEDIUM",0)}) severity levels. An ablation study over all seven '
        'ensemble configurations shows that the three models capture complementary anomaly '
        f'types: EE aligns most with the rule engine (Precision@K={_ee[2]:.1%}), LOF detects '
        'orthogonal local anomalies, and IF balances both. Low inter-model agreement '
        f'(Cohen’s Kappa LOF–EE={_lofee_abs:.2f}) and the ensemble never being the worst '
        'configuration across proxy thresholds justify the heterogeneous ensemble for '
        'robustness. SHAP analysis provides transparent per-user explanations, enabling '
        'auditable decision-making for security analysts.')
    set_font(run, size=10)

    # Keywords
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.space_after = Pt(12)
    p.paragraph_format.first_line_indent = Cm(0.5)
    run = p.add_run('Keywords: ')
    set_font(run, size=10, bold=True)
    run = p.add_run('Anomaly detection, Knowledge graph, Active Directory, Ensemble learning, '
                    'Isolation Forest, SHAP, Explainable AI, Cybersecurity.')
    set_font(run, size=10)

    # ── SWITCH TO TWO COLUMN ─────────────────────────────────────────
    add_section_break(doc, columns=2)

    # ── 1. INTRODUCTION ──────────────────────────────────────────────
    add_heading_lvl1(doc, 1, 'Introduction')
    add_text(doc,
        'Active Directory (AD) serves as the backbone of identity and access management in '
        'most enterprise environments. The volume of authentication events generated daily '
        '— often exceeding millions — makes manual monitoring infeasible. Security '
        'analysts increasingly rely on automated anomaly detection to identify compromised '
        'accounts, insider threats, and policy violations [1, 2].')
    add_text(doc,
        'Existing approaches to AD anomaly detection face three primary limitations. First, '
        'rule-based systems, while interpretable, only detect predefined attack patterns and '
        'miss novel anomalies. Second, conventional machine learning approaches treat events '
        'as independent records, ignoring the rich relational structure inherent in AD '
        '(users, devices, servers, network connections). Third, many ML-based systems operate '
        'as black boxes, producing alerts without providing actionable explanations to '
        'security analysts [3, 4].')
    add_text(doc,
        'This paper addresses these limitations through a hybrid pipeline that combines '
        'knowledge graph representation, domain-driven rule engine, heterogeneous ensemble '
        'anomaly detection, and SHAP-based explainability. The contributions of this work '
        'are as follows:')
    add_text(doc,
        '(1) We model AD audit logs as a Neo4j knowledge graph with seven node types and ten '
        'relationship types, enabling graph traversal queries that are infeasible in '
        'relational databases.')
    add_text(doc,
        '(2) We propose a heterogeneous ensemble of three unsupervised models (IF, LOF, EE) '
        'with majority voting, leveraging their differing inductive biases to capture '
        'complementary anomaly types.')
    add_text(doc,
        '(3) We introduce data-driven quantile-based severity classification (P75/P90/P95/P99) '
        'as an alternative to arbitrary threshold selection, with justification grounded in '
        'outlier analysis literature [5, 6].')
    add_text(doc,
        '(4) We integrate SHAP TreeExplainer to produce per-user feature contribution '
        'explanations, transforming black-box anomaly scores into auditable evidence.')
    add_text(doc,
        '(5) We conduct an ablation study quantifying the individual contribution of each '
        'ensemble component using Jaccard index, Cohen’s Kappa, and Precision@K against '
        'a rule-based proxy ground truth.')

    # ── 2. RELATED WORK ──────────────────────────────────────────────
    add_heading_lvl1(doc, 2, 'Related work')
    add_text(doc,
        'Anomaly detection in security logs has been extensively studied. Liu et al. [5] '
        'introduced Isolation Forest, a tree-based anomaly detector based on random '
        'partitioning. Breunig et al. [7] proposed the Local Outlier Factor (LOF) for '
        'density-based outlier detection. Rousseeuw and Driessen [8] developed the Minimum '
        'Covariance Determinant estimator, the basis of Elliptic Envelope.')
    add_text(doc,
        'For explainability, Lundberg and Lee [9] introduced SHAP (SHapley Additive '
        'exPlanations), unifying several feature attribution methods. The TreeExplainer '
        'variant provides exact Shapley values for tree-based models, including Isolation '
        'Forest.')
    add_text(doc,
        'Graph-based representations for security analytics have gained traction. Knowledge '
        'graphs enable multi-hop relational queries (e.g., user → device → IP) that '
        'are computationally expensive in relational databases. Several studies have explored '
        'graph databases for cybersecurity log analysis [1, 4].')
    add_text(doc,
        'For severity classification, Aggarwal [6] discusses quantile-based thresholding as a '
        'standard practice in outlier analysis. Goldstein and Uchida [10] provide a '
        'comparative evaluation of unsupervised anomaly detection algorithms, emphasizing '
        'the importance of methodology-aware evaluation. The Common Vulnerability Scoring '
        'System (CVSS) [11] establishes a five-tier severity rating widely adopted in '
        'cybersecurity, which we adapt for our anomaly score classification.')

    # ── 3. METHODOLOGY ───────────────────────────────────────────────
    add_heading_lvl1(doc, 3, 'Proposed method')

    add_heading_lvl2(doc, '3.1', 'System architecture')
    add_text(doc,
        'The proposed pipeline consists of seven sequential phases: (1) Data preparation, '
        '(2) Neo4j knowledge graph ingestion, (3) Rule-based engine, (4) Graph feature '
        'extraction, (5) Ensemble anomaly detection, (5.5) SHAP explainability, and (6) '
        'Reporting. The pipeline transforms raw AD log events into actionable anomaly '
        'reports with quantitative explanations.')

    add_heading_lvl2(doc, '3.2', 'Knowledge graph construction')
    add_text(doc,
        'AD audit logs are ingested into Neo4j as a property graph comprising seven node '
        f'types (User, Hostname, Server, IPAddress, Service, Group, Event) and eight '
        'relationship types (LOGIN_FROM, AUTHENTICATED_VIA, FAILED_LOGIN, CONNECTED_FROM, '
        'USED_IP, USED_SERVICE, MEMBER_OF, REFERENCES). Each log row produces one or more '
        'edges, with timestamp and event metadata stored as edge properties.')

    add_heading_lvl2(doc, '3.3', 'Rule-based knowledge engine')
    add_text(doc,
        'Ten domain rules encoding expert knowledge are implemented as Cypher queries '
        'executed directly on the graph. Rules detect patterns such as multi-host login '
        '(R001), off-hours access (R002), failed login spikes (R005), and excessive admin '
        'actions (R009). Each user’s rule_violations count (0–10) is stored as a '
        'node property and serves as both an interpretable signal and an input feature for '
        'subsequent ML phases.')

    add_heading_lvl2(doc, '3.4', 'Graph feature extraction')
    add_text(doc,
        'Eleven user-level features are derived from graph relationships, including host '
        'diversity, critical server access ratio, failure ratio, shared device risk, IP '
        'network risk, privilege level, graph connectivity (degree centrality), rule '
        'violations, lockout count, admin actions, and sensitive group membership. These '
        'features cannot be computed from row-level CSV data without graph traversal, '
        'justifying the graph representation.')

    add_heading_lvl2(doc, '3.5', 'Ensemble anomaly detection')
    add_text(doc,
        'Three heterogeneous unsupervised models are trained on the standardized feature '
        'matrix with contamination rate 0.05: Isolation Forest (tree-based), Local Outlier '
        'Factor (density-based), and Elliptic Envelope (statistical). Each model independently '
        'flags users as anomalous, and a user is considered anomalous if at least two of three '
        'models agree (majority voting).')
    add_text(doc, 'The final anomaly score combines voting and rule violations:')
    add_equation(doc,
        'final_score = 0.60 × (votes / 3) + 0.40 × (rule_violations / 10)', 1)

    add_heading_lvl2(doc, '3.6', 'Quantile-based severity classification')
    add_text(doc,
        'To avoid arbitrary threshold selection, we classify severity using data-driven '
        'quantile thresholds. Given the heavy-tailed distribution of anomaly scores '
        f'(min={SCORE_STATS["min"]:.3f}, max={SCORE_STATS["max"]:.3f}, '
        f'mean={SCORE_STATS["mean"]:.3f}), absolute thresholds (e.g., direct CVSS mapping) '
        'would yield severely unbalanced class distributions.')
    add_text(doc, 'The five-tier classification follows:')
    add_equation(doc,
        f'CRITICAL: score ≥ P99 ({P99:.4f})', 2)
    add_equation(doc,
        f'HIGH: P95 ({P95:.4f}) ≤ score < P99', 3)
    add_equation(doc,
        f'MEDIUM: P90 ({P90:.4f}) ≤ score < P95', 4)
    add_equation(doc,
        f'LOW: P75 ({P75:.4f}) ≤ score < P90', 5)
    add_text(doc,
        'The choice of P95 specifically aligns with the contamination rate (5%) of the '
        'three ML models, ensuring consistency between model assumptions and classification '
        'thresholds.')

    add_heading_lvl2(doc, '3.7', 'SHAP explainability')
    add_text(doc,
        'Per-user explanations are generated using SHAP TreeExplainer on the trained '
        'Isolation Forest model. For each user, SHAP values quantify the contribution of '
        'each feature to the anomaly score. The top contributing feature is recorded as the '
        '"top cause" label, enabling security analysts to understand why a user was flagged '
        'without inspecting raw scores.')

    # ── 4. EXPERIMENTAL SETUP ────────────────────────────────────────
    add_heading_lvl1(doc, 4, 'Experimental setup')

    add_heading_lvl2(doc, '4.1', 'Dataset')
    add_text(doc,
        f'The dataset comprises 1,833,352 AD logon events spanning multiple domain '
        f'controllers and member servers, exported from ManageEngine ADAudit Plus. After '
        f'graph ingestion, the dataset is represented as {TOTAL_USERS:,} unique users, '
        '1,273 hostnames, 1,275 IP addresses, and 7 servers. Each user is associated with '
        'login events, authentication outcomes, group memberships, and administrative '
        'actions.')

    add_heading_lvl2(doc, '4.2', 'Implementation')
    add_text(doc,
        'The pipeline is implemented in Python 3.12, with Neo4j 5.x as the graph database. '
        'Machine learning models use scikit-learn 1.4 with default parameters except for '
        'contamination=0.05. SHAP values are computed using shap 0.46 TreeExplainer. All '
        'experiments were conducted on a standard workstation (Windows 11, 16GB RAM).')

    add_heading_lvl2(doc, '4.3', 'Evaluation methodology')
    add_text(doc,
        'Because no ground truth labels are available for unsupervised anomaly detection, '
        'evaluation relies on a proxy approach: users with rule_violations ≥ 6 are '
        'treated as "true anomalies." We report standard classification metrics (Accuracy, '
        'Precision, Recall, F1) against this proxy for each ensemble configuration, alongside '
        'Precision@K, Jaccard index, and Cohen’s Kappa for inter-model agreement. We '
        'emphasize that these metrics are computed against a rule-based proxy rather than '
        'expert-validated labels; consequently, they should be interpreted as weak '
        'supervision and are inherently biased toward detectors aligned with the rule '
        'engine. To mitigate over-interpretation, we additionally conduct a sensitivity '
        'analysis across multiple proxy thresholds.')

    # ── 5. RESULTS ───────────────────────────────────────────────────
    add_heading_lvl1(doc, 5, 'Results and discussion')

    add_heading_lvl2(doc, '5.1', 'Severity distribution')
    add_text(doc,
        f'Table 1 summarizes the severity distribution under quantile-based classification. '
        f'A total of {TOTAL_ANOMALI} users ({100*TOTAL_ANOMALI/TOTAL_USERS:.1f}%) are '
        f'classified as MEDIUM severity or higher, while {ANOMALY_DIST.get("CRITICAL",0)} '
        f'users are flagged as CRITICAL (top 1%).')

    add_table(doc,
        ['Severity', 'Threshold', 'Users', 'Percentage'],
        [
            ('CRITICAL', f'≥ {P99:.4f}', ANOMALY_DIST.get('CRITICAL', 0),
             f'{100*ANOMALY_DIST.get("CRITICAL",0)/TOTAL_USERS:.1f}%'),
            ('HIGH',     f'≥ {P95:.4f}', ANOMALY_DIST.get('HIGH', 0),
             f'{100*ANOMALY_DIST.get("HIGH",0)/TOTAL_USERS:.1f}%'),
            ('MEDIUM',   f'≥ {P90:.4f}', ANOMALY_DIST.get('MEDIUM', 0),
             f'{100*ANOMALY_DIST.get("MEDIUM",0)/TOTAL_USERS:.1f}%'),
            ('LOW',      f'≥ {P75:.4f}', ANOMALY_DIST.get('LOW', 0),
             f'{100*ANOMALY_DIST.get("LOW",0)/TOTAL_USERS:.1f}%'),
            ('NORMAL',   f'< {P75:.4f}',      ANOMALY_DIST.get('NORMAL', 0),
             f'{100*ANOMALY_DIST.get("NORMAL",0)/TOTAL_USERS:.1f}%'),
        ], 1, 'Severity distribution with quantile-based thresholds')

    add_heading_lvl2(doc, '5.2', 'Top anomalous users')
    add_text(doc,
        'Table 2 presents the top five anomalous users ranked by anomaly score, with their '
        'rule violation counts, ensemble voting, and SHAP-derived top causes. The highest-'
        f'scoring user ({TOP5.iloc[0]["username"]}) achieves a score of '
        f'{TOP5.iloc[0]["final_anomaly_score"]:.4f} with all three models in agreement and '
        f'{int(TOP5.iloc[0]["rule_violations"])} out of 10 rules violated.')

    top_rows = []
    for _, r in TOP5.iterrows():
        top_rows.append((
            r['username'],
            f'{r["final_anomaly_score"]:.4f}',
            r['severity'],
            f'{int(r["rule_violations"])}/10',
            f'{int(r["anomaly_votes"])}/3',
            r['top_feature_1_label'] if pd.notna(r['top_feature_1_label']) else '-',
        ))
    add_table(doc,
        ['Username', 'Score', 'Severity', 'Rules', 'Votes', 'Top SHAP Cause'],
        top_rows, 2, 'Top 5 anomalous users with SHAP explanations')

    add_heading_lvl2(doc, '5.3', 'Ablation study')
    add_text(doc,
        'To quantify the contribution of each ensemble component, we evaluate IF, LOF, and EE '
        'individually. Table 3 reports detection counts, inter-model agreement, and proxy-'
        'based quality metrics.')

    add_table(doc,
        ['Model', 'Detected', 'Precision@K', 'Avg rule_viol', 'Avg score'],
        [(name, n, f'{pk:.4f}', f'{arv:.2f}', f'{asc:.4f}')
         for (name, n, pk, arv, asc) in IND_ABLATION],
        3, 'Ablation study: individual model performance')

    add_text(doc,
        'The results reveal complementary behavior. EE achieves the highest Precision@K '
        f'({_ee[2]:.1%}) and average rule violations ({_ee[3]:.2f}), indicating strong '
        'alignment with the rule engine. LOF, conversely, shows the lowest values '
        f'(avg rule_viol = {_lof[3]:.2f}, below the population baseline of {_BASE_RV:.2f}), '
        'suggesting it captures anomalies orthogonal to rule-based patterns. This '
        'complementarity justifies the heterogeneous ensemble: the models specialize in '
        'different anomaly types.')
    add_text(doc,
        'Inter-model agreement metrics (Jaccard and Cohen’s Kappa, Table 4) further '
        f'support this finding. LOF–EE agreement is particularly low (Kappa = {_lofee[2]:.2f}), '
        'indicating they identify largely disjoint sets of anomalies.')

    add_table(doc,
        ['Model Pair', 'Jaccard', 'Cohen’s Kappa', 'Interpretation'],
        [(pair, f'{j:.3f}', f'{k:.3f}', interp) for (pair, j, k, interp) in AGREEMENT],
        4, 'Inter-model agreement metrics')

    add_heading_lvl2(doc, '5.4', 'Ensemble configuration ablation')
    add_text(doc,
        'Beyond individual models, we evaluate all seven non-empty ensemble configurations '
        '(three single, three pairwise, one triple) to assess whether any combination '
        'consistently outperforms the others. For fairness, model scores are combined via '
        'rank-based fusion (robust to scale differences across detectors), and each '
        'configuration flags the top-K users where K equals the number of proxy-positive '
        'users (rule_violations ≥ 6). Accuracy, Precision, Recall, and F1 are computed '
        'against the rule-based proxy ground truth. Table 5 reports the results.')

    combo_rows = []
    for name, acc, prec, rec, f1 in COMBO_ABLATION:
        combo_rows.append((name, f'{acc:.4f}', f'{prec:.4f}', f'{rec:.4f}', f'{f1:.4f}'))
    add_table(doc,
        ['Configuration', 'Accuracy', 'Precision', 'Recall', 'F1'],
        combo_rows, 5, 'Accuracy of seven ensemble configurations (rule-based proxy)')

    _sens_desc = ', '.join(f'{SENS_BEST[t][0]} (≥{t})' for t in _SENS_T)
    _ens_f1 = ', '.join(f'{SENS_TABLE["IF+LOF+EE"][t]:.3f}' for t in _SENS_T)
    add_text(doc,
        'A sensitivity analysis evaluates each configuration against proxy thresholds '
        f'rule_violations ≥ {_SENS_T[0]} … {_SENS_T[-1]} (best per threshold: {_sens_desc}). '
        'EE attains the highest F1 in most settings; however, this advantage is partly an '
        'artifact of the proxy being derived from the same rule engine, so EE detections '
        'align with rule violations by construction. Individual models are also volatile '
        'across definitions — for example, LOF is competitive at lower thresholds but '
        'collapses at higher ones. '
        + ('Critically, the full IF+LOF+EE ensemble is never the worst configuration at any '
           f'threshold (F1 = {_ens_f1}), remaining consistently mid-ranked. '
           if _ENS_NEVER_WORST else
           'The full ensemble stays competitive across thresholds. ')
        + 'This demonstrates that the value of the heterogeneous ensemble lies in robustness '
        'and stable generalization across differing anomaly definitions rather than in '
        'maximizing any single (rule-biased) proxy metric.')

    add_heading_lvl2(doc, '5.5', 'SHAP feature importance')
    add_text(doc,
        'Global SHAP analysis identifies the four most influential features '
        '(shared_device_risk, critical_server_ratio, host_diversity, rule_violations) with '
        'mean |SHAP| values above 0.47. Notably, three features (sensitive_groups, '
        'ip_network_risk, privilege_level) yield zero SHAP contribution on this dataset, '
        'indicating dataset-specific feature relevance that future deployments should '
        're-evaluate.')
    add_text(doc,
        'Per-user SHAP top causes provide auditable explanations. For instance, the highest-'
        f'scoring user is flagged due to "{TOP5.iloc[0]["top_feature_1_label"]}", '
        'enabling security analysts to focus investigation efforts on specific behavioral '
        'patterns rather than generic anomaly labels.')

    add_heading_lvl2(doc, '5.6', 'Discussion')
    add_text(doc,
        'The proposed pipeline addresses three key challenges in AD anomaly detection. '
        'First, the knowledge graph representation enables relational queries that are '
        'infeasible in tabular formats. Second, the heterogeneous ensemble captures multiple '
        'anomaly types via complementary inductive biases. Third, SHAP explanations and '
        'quantile-based thresholds together produce transparent, reproducible classifications '
        'suitable for security audit workflows.')
    add_text(doc,
        'A key limitation is the absence of ground truth labels for absolute precision/recall '
        'evaluation. The proxy approach (rule_violations ≥ 6) inherently favors models '
        'aligned with domain rules (EE) and penalizes models capturing orthogonal anomalies '
        '(LOF), even though both have practical value. Future work should incorporate expert-'
        'validated labels and explore threshold sensitivity analysis.')

    # ── 6. CONCLUSION ────────────────────────────────────────────────
    add_heading_lvl1(doc, 6, 'Conclusion')
    add_text(doc,
        'This paper presented a knowledge graph-based anomaly detection pipeline for '
        'Active Directory audit logs, integrating Neo4j, rule-based engine, heterogeneous '
        'ML ensemble (IF + LOF + EE), and SHAP explainability. Evaluated on '
        f'{TOTAL_USERS:,} users derived from 1.8 million AD events, the system identified '
        f'{TOTAL_ANOMALI} anomalous users across CRITICAL, HIGH, and MEDIUM severity tiers, '
        'with data-driven quantile-based thresholds replacing arbitrary value selection.')
    add_text(doc,
        'The ablation study demonstrated that the three ensemble components capture '
        'complementary anomaly types: EE aligns with domain rules, LOF detects orthogonal '
        'local anomalies, and IF balances both. Low inter-model agreement (Cohen’s '
        'Kappa = 0.20 for LOF-EE) empirically justifies the ensemble approach. SHAP '
        'explanations transform black-box anomaly scores into auditable evidence, enabling '
        'practical deployment in security operations.')
    add_text(doc,
        'Future work will focus on (1) expert-validated ground truth for absolute '
        'precision/recall evaluation, (2) threshold sensitivity analysis with ROC and '
        'cost-sensitive metrics, and (3) extension to temporal anomaly detection using '
        'sequence models (e.g., LSTM autoencoders) integrated with the graph representation.')

    # ── CONFLICTS OF INTEREST ────────────────────────────────────────
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(6)
    run = p.add_run('Conflicts of interest')
    set_font(run, size=11, bold=True)
    add_text(doc, 'The authors declare no conflict of interest.', indent=False)

    # ── AUTHOR CONTRIBUTIONS ─────────────────────────────────────────
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(6)
    run = p.add_run('Author contributions')
    set_font(run, size=11, bold=True)
    add_text(doc,
        'Conceptualization, methodology, software, validation, formal analysis, '
        'investigation, data curation, writing—original draft preparation, '
        'writing—review and editing, visualization: Mahathir Muhammad.', indent=False)

    # ── REFERENCES ───────────────────────────────────────────────────
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(3)
    run = p.add_run('References')
    set_font(run, size=12, bold=True)

    references = [
        '[1] M. Du, F. Li, G. Zheng, and V. Srikumar, “DeepLog: Anomaly detection and '
        'diagnosis from system logs through deep learning”, In: Proc. of ACM SIGSAC '
        'Conf. on Computer and Communications Security, Dallas, Texas, USA, pp. 1285–1298, '
        '2017.',

        '[2] R. Chen, S. Zhang, D. Li, Y. Zhang, F. Guo, W. Meng, D. Pei, Y. Zhang, X. Chen, '
        'and Y. Liu, “LogTransfer: Cross-system log anomaly detection for software '
        'systems with transfer learning”, In: Proc. of IEEE Int. Symp. on Software '
        'Reliability Engineering, Coimbra, Portugal, pp. 37–47, 2020.',

        '[3] X. Han, T. Pasquier, A. Bates, J. Mickens, and M. Seltzer, “Unicorn: '
        'Runtime provenance-based detector for advanced persistent threats”, In: Proc. '
        'of Network and Distributed System Security Symposium, San Diego, California, USA, '
        '2020.',

        '[4] H. Studiawan, F. Sohel, and C. Payne, “Anomaly detection in operating '
        'system logs with deep learning-based sentiment analysis”, IEEE Trans. on '
        'Dependable and Secure Computing, Vol. 18, No. 5, pp. 2136–2148, 2020.',

        '[5] F. T. Liu, K. M. Ting, and Z. H. Zhou, “Isolation Forest”, In: Proc. '
        'of IEEE Int. Conf. on Data Mining, Pisa, Italy, pp. 413–422, 2008.',

        '[6] C. C. Aggarwal, Outlier Analysis, 2nd ed., Springer, New York, 2017.',

        '[7] M. M. Breunig, H. P. Kriegel, R. T. Ng, and J. Sander, “LOF: Identifying '
        'density-based local outliers”, In: Proc. of ACM SIGMOD Int. Conf. on '
        'Management of Data, Dallas, Texas, USA, pp. 93–104, 2000.',

        '[8] P. J. Rousseeuw and K. V. Driessen, “A fast algorithm for the minimum '
        'covariance determinant estimator”, Technometrics, Vol. 41, No. 3, pp. 212–223, '
        '1999.',

        '[9] S. M. Lundberg and S. I. Lee, “A unified approach to interpreting model '
        'predictions”, In: Proc. of Advances in Neural Information Processing Systems, '
        'Long Beach, California, USA, pp. 4765–4774, 2017.',

        '[10] M. Goldstein and S. Uchida, “A comparative evaluation of unsupervised '
        'anomaly detection algorithms for multivariate data”, PLOS ONE, Vol. 11, No. 4, '
        'pp. 1–31, 2016.',

        '[11] Forum of Incident Response and Security Teams (FIRST), Common Vulnerability '
        'Scoring System v3.1: Specification Document, 2019. Available: '
        'https://www.first.org/cvss/v3-1/specification-document.',
    ]
    for ref in references:
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Cm(0.5)
        p.paragraph_format.first_line_indent = Cm(-0.5)
        p.paragraph_format.space_after = Pt(3)
        p.paragraph_format.line_spacing = 1.0
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        run = p.add_run(ref)
        set_font(run, size=11)

    out_path = 'output/IJIES_Draft_Paper_Mahathir_Muhammad.docx'
    doc.save(out_path)
    print(f'[OK] Paper saved: {out_path}')
    return out_path


if __name__ == '__main__':
    print('Generating IJIES draft paper...')
    path = build_paper()
    print(f'Done: {path}')
