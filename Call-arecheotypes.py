import json
import os
import re
import pandas as pd

FAJL = "eu_TAD_revision_hozzaszolasok_900.json"
SRC = next((p for p in (f"/content/{FAJL}", f"/mnt/user-data/uploads/{FAJL}", FAJL)
            if os.path.exists(p)), FAJL)
KIM = "/content" if os.path.isdir("/content") else "/mnt/user-data/outputs"

# ═══════════════════════════════════════════════════ 1. BETÖLTÉS, HU SZŰRÉS
def load(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        head = f.read(2048); f.seek(0)
        if head.lstrip().startswith("["):
            rows = json.load(f)
        else:
            for line in f:
                line = line.strip().rstrip(",")
                if line and line not in "[]":
                    rows.append(json.loads(line))
    return pd.json_normalize(rows)


nyers = load(SRC)
nyers["language"] = nyers["language"].astype(str).str.upper().str.strip()
df = nyers[nyers["language"].eq("HU")].copy().reset_index(drop=True)
print(f"Összes hozzászólás: {len(nyers):,}  →  magyar nyelvű: {len(df):,}")

df["t"] = df["feedback"].fillna("").astype(str).str.lower()
df["szoszam"] = df["t"].str.split().str.len()
df["datum"] = pd.to_datetime(df["dateFeedback"], format="%Y/%m/%d %H:%M:%S", errors="coerce")

# ═══════════════════════════════════════ 2. ÖT CSOPORT — SZIGORÚ ÖNAZONOSÍTÁS
C1 = "1. Dohánytermelő / gyártó"
C2 = "2. Kiskereskedő (dohánybolt)"
C3 = "3. Fogyasztó / természetes személy"
C4 = "4. Civil szervezet/NGO"
C5 = "5. Egészségügyi szakértő"

ONAZONOSITAS = {
    C1: (r"(gyártóként|termelőként|dohánytermesztőként|gazdálkodóként|termesztőként)"
         r"|(gyártó|termelő|dohánytermesztő|gazdálkodó|dohányos gazda)\s+vagyok"
         r"|mint\s+(gyártó|termelő|dohánytermesztő|gazdálkodó)"
         r"|(ültetvényünk|földjeink|földjeinken)"
         r"|dohányt term(esztek|elünk|esztünk)|dohánytermesztéssel foglalkoz"),
    C2: (r"(trafikosként|eladóként|kiskereskedőként|kereskedőként|üzletvezetőként|boltvezetőként|pénztárosként)"
         r"|(trafikos|eladó|kiskereskedő|kereskedő|üzletvezető|boltvezető|trafikvezető)\s+vagyok"
         r"|mint\s+(trafikos|eladó|kiskereskedő|kereskedő|boltvezető|elkötelezett keresked\w+)"
         r"|(a|az)\s+(boltom|üzletem|trafikom|dohányboltom)"
         r"|(boltomban|üzletemben|trafikomban)"
         r"|(trafikban|dohányboltban|nemzeti dohányboltban|boltban|üzletben)\s+dolgoz(om|ok|unk)"
         r"|(vevőim|vásárlóim|ügyfeleim|törzsvásárlóim)"),
    C4: (r"(egyesületünk|alapítványunk|szövetségünk|szervezetünk|kamaránk|szakszervezetünk)\b"
         r"|(egyesület|alapítvány|szövetség|szervezet|szakszervezet)\w*\s+nevében"
         r"|civil szervezetként|érdekképviseletként"),
    C5: (r"(orvosként|ápolóként|gyógyszerészként|védőnőként|kutatóként|szakorvosként|szakértőként|fogorvosként)"
         r"|(orvos|háziorvos|szakorvos|tüdőgyógyász|onkológus|ápoló|gyógyszerész|védőnő|fogorvos)\s+vagyok"
         r"|mint\s+(orvos|háziorvos|ápoló|gyógyszerész|egészségügyi dolgozó|szakember)"
         r"|(a\s+)?betegeim|pácienseim|(rendelőmben|kórházban dolgoz(om|ok))"
         r"|egészségügyben dolgoz(om|ok)"),
}
# KÉTÉRTELMŰ első személyű üzleti kifejezések: önmagukban NEM azonosítanak.
# "gazdaságunk" = farm VAGY nemzetgazdaság; "vállalkozásunk" = trafik VAGY ültetvény.
# Csak akkor fogadjuk el, ha a közelben (±200 karakter) ott a szerepkontextus is.

KETERTELMU = r"(cégünk|vállalatunk|vállalkozásunk|üzemünk|gyárunk|szövetkezetünk|gazdaságunk|családi vállalkozás)"
KONTEXTUS = {
    C1: r"dohánytermeszt|termelés|termeszt|ültetvény|hektár|dohánylevél|feldolgoz|gyárt|betakarít|földjein",
    C2: r"trafik|dohánybolt|bolt|üzlet|eladás|értékesít|kiskereskede|vevő|vásárló|pult",
}
ABLAK = 200


def kontextusos_talalat(txt, ctx_pat):
    """Kétértelmű üzleti kifejezés + a közelben szerepkontextus."""
    for m in re.finditer(nc(KETERTELMU), txt):
        a, b = max(0, m.start() - ABLAK), min(len(txt), m.end() + ABLAK)
        if re.search(ctx_pat, txt[a:b]):
            return "…" + re.sub(r"\s+", " ", txt[max(0, m.start() - 45):m.end() + 45]) + "…"
    return None


# A természetes személy (C3) a maradék, de az önazonosított fogyasztót jelöljük:
FOGYASZTO_ONAZ = (r"(dohányzom|cigizem|cigizek|cigiztem||vape-et szívok|gőzölök|vapelek|snüszözök)"
                  r"|(leszokt(am|unk))|(áttértem|átálltam)"
                  r"|(fogyasztóként|dohányosként|felnőtt fogyasztóként|használóként)"
                  r"|(én\s+is\s+)?(használom|használok)\s+(ilyet|ezeket|e-cigit|hevített)"
                  r"|\d+\s*(éve|év óta)\s*(dohányz|cigiz|gőzöl|vape|nem gyújt)")

USERTYPE = {  # portál-metaadat: erősebb, mint a szöveg
    "COMPANY": C1, "BUSINESS_ASSOCIATION": C1,
    "NGO": C4, "ENVIRONMENTAL_ORGANISATION": C4, "CONSUMER_ORGANISATION": C4, "TRADE_UNION": C4,
    "ACADEMIC_RESEARCH_INSTITTUTION": C5, "PUBLIC_AUTHORITY": C5,   # a portál elgépelése
}


def nc(pat: str) -> str:
    """A csoportosított zárójeleket nem-elfogóvá teszi (pandas figyelmeztetés + gyorsabb)."""
    return re.sub(r"\((?!\?)", "(?:", pat)


def elso_talalat(pat, txt, ablak=45):
    """Visszaadja az első illeszkedést a környezetével — kézi validáláshoz."""
    m = re.search(pat, txt)
    if not m:
        return None
    a, b = max(0, m.start() - ablak), min(len(txt), m.end() + ablak)
    return "…" + re.sub(r"\s+", " ", txt[a:b]) + "…"


def csoportosit(sor):
    txt, ut = sor["t"], str(sor.get("userType", ""))
    talalatok = {cs: elso_talalat(nc(p), txt) for cs, p in ONAZONOSITAS.items()}
    for cs, ctx in KONTEXTUS.items():                 # kétértelmű kifejezések feloldása
        if not talalatok[cs]:
            talalatok[cs] = kontextusos_talalat(txt, ctx)

    if ut in USERTYPE:
        cs, ev = USERTYPE[ut], "metaadat (userType)"
        if ut in ("COMPANY", "BUSINESS_ASSOCIATION") and talalatok[C2]:
            cs = C2                                   # kiskereskedelmi cég, nem gyártó
        biz = talalatok.get(cs) or f"userType={ut}"
    elif any(talalatok.values()):
        # ha több szerep is megjelenik, a leghosszabb illeszkedés (leginformatívabb) nyer
        cs = max((k for k, v in talalatok.items() if v), key=lambda k: len(talalatok[k]))
        ev, biz = "önazonosítás", talalatok[cs]
    else:
        cs, ev, biz = C3, "maradékkategória (természetes személy)", "-"

    return pd.Series([cs, ev, biz, "|".join(sorted(k for k, v in talalatok.items() if v)) or "-"])


df[["csoport", "evidencia", "bizonyitek", "osszes_szerep"]] = df.apply(csoportosit, axis=1)
df["fogyasztoi_onazonositas"] = df["t"].str.contains(nc(FOGYASZTO_ONAZ), regex=True)

# ═══════════════════════════════════ 3. POZÍCIÓ (mellette / ellene / differenciált)
NEG = r"(ne|nem|sem)\s+\w{0,12}\s?(tilt|korlátoz|szigorít)\w*"
ELLEN1 = (r"nem értek egyet|ellenzem|elutasítom|ne tilts|ne korlátoz|ne szigorít|túlszabályoz"
          r"|túlzott(an)? (szigorú|szabályoz|korlátoz|tilt)|felesleges tilalom|nem kell (több )?szigorít"
          r"|nem támogatom|ne vezessen be|nincs (rá )?szükség|semmi szükség|milyen jogon|értelmetlen"
          r"|kontraproduktív|visszaüt|rossz irány|hibásnak tartom|aggaszt|aggódom|aggály|aggodalm"
          r"|frusztrál|nem szándékolt következm|nem hozt(a|ák) a várt eredményt|nem érté?k? el (a )?célj"
          r"|nem szeretném|nem akarom|ne szűnjön meg|nagyon rossz|elhibázott")
MELLETT1 = (r"támogatom|üdvözlöm|be kell tiltani|tiltsák be|szigorúbb szabályozás(ra van szükség|t)"
            r"|szigorítani kell|helyeslem|egyetértek a javaslattal|erősebb védelem|indokolt a tilalom"
            r"|szükség van a szabályozásra|jó irány|fontos lépés|végre")
DIFF1 = (r"kockázatarányos|kockázati alapú|különbséget kell tenni|ne (kerüljön|tegyék) egy kalap alá"
         r"|arányos szabályoz|differenciál|szabályozni igen(,)? tiltani nem|nem azonos a cigarettával"
         r"|szabályozott (de )?elérhető")

IPAR_ERV = {   # érvcsaládok — a T2 szintű pozíciókódolás és a D3 alapja
    "A1 feketepiac": r"feketepiac|fekete piac|csempész|illegális (piac|kereskede|termék|beszerz)|zugárus|külföldről hozz",
    "A2 gazdaság/munkahely": r"munkahely|megélhetés|kisvállalkoz|kkv|forgalom (csökken|kiesés)|bezár|adóbevétel|gazdasági (kár|hatás)|elbocsát",
    "A3 felnőtt választás": r"választás szabadság|szabadon dönt|felnőtt.{0,25}(dönt|válasz|jog)|nagykorú|gyámkod|paternal|szuverenitás|brüsszel",
    "A4 ártalomcsökkentés": r"ártalomcsökkent|kevésbé (káros|ártalmas)|alternatív (nikotin|dohány)|leszokásban segít|füstmentes",
}
EU_ERV = {
    "H1 ifjúságvédelem": r"gyermek|gyerek|fiatalkorú|kiskorú|18 éven aluli|ifjúságvédelem|ízek vonzz|kapudrog",
    "H2 népegészségügy": r"népegészségügy|who|fctc|megelőzés|prevenció|rák|halálozás|passzív dohányz|betegségteher",
    "H3 marketing/csomagolás": r"reklámtilalom|egységes csomagolás|influenszer",
    "H4 környezet": r"környezetszennyez|hulladék|eldobható.{0,20}(szemét|akkumulátor)|csikk",
}
df["n_ipar"] = sum(df["t"].str.contains(nc(p), regex=True).astype(int) for p in IPAR_ERV.values())
df["n_eu"] = sum(df["t"].str.contains(nc(p), regex=True).astype(int) for p in EU_ERV.values())

MELLETTE, ELLENE = "MELLETTE (szigorítás-párti)", "ELLENE (szigorítás-ellenes)"
DIFF, VEGYES, NINCS = "DIFFERENCIÁLT (kockázatarányos)", "VEGYES / ambivalens", "NEM ÉRTELMEZHETŐ"


def pozicio(sor):
    raw = sor["t"]
    if re.search(nc(DIFF1), raw):
        return pd.Series([DIFF, "T1 explicit"])
    e = len(re.findall(nc(ELLEN1), raw))
    m = len(re.findall(nc(MELLETT1), re.sub(nc(NEG), " ", raw)))
    if e != m:
        return pd.Series([ELLENE if e > m else MELLETTE, "T1 explicit"])
    if e:
        return pd.Series([VEGYES, "T1 explicit"])
    e, m = sor["n_ipar"], sor["n_eu"]
    if e != m:
        return pd.Series([ELLENE if e > m else MELLETTE, "T2 érvkészlet"])
    if e:
        return pd.Series([VEGYES, "T2 érvkészlet"])
    return pd.Series([NINCS, "-"])


df[["pozicio", "pozicio_szint"]] = df.apply(pozicio, axis=1)

# ═══════════════════════════════════════════ 4. ÚJ LEFÚRÁSI PONTOK (D1–D7)
# D1 — melyik szabályozási eszköz jelenik meg (a Bizottság szakpolitikai opciói)
D1_ESZKOZ = {
    "ízesítés-tilalom": r"ízesít|ízek|aroma|mentol|menta ízű|gyümölcsös íz",
    "egységes csomagolás": r"egységes csomagolás|egyen[- ]?csomagolás|semleges csomagolás|plain packaging|csomagolás egységes",
    "eldobható e-cigaretta": r"eldobható|egyszer használatos|disposable",
    "nikotinpárna / új termékek": r"nikotinpárna|nikotin tasak|pouch|snüsz|snus",
    "hevített dohánytermék": r"hevített|heets|iqos|glo|dohányhevít",
    "online reklám / influenszer": r"reklám|marketing|influenszer|közösségi média|hirdet",
    "adó / ár": r"jövedéki|adó|áremel|drágul|ár(a|ak) (emelked|növek)",
    "értékesítési korlátozás / hozzáférés": r"értékesítési pont|árusítás korlátoz|kiskereskedelmi (tilalom|korlát)|hol lehet vásárolni|beszerezhető",
}
# D2 — melyik termékkategóriát VÉDI (a védelem jele: a termék + pozitív/leszokási keret)
D2_TERMEK = {
    "hevített dohánytermék": r"hevített|iqos|glo|heets",
    "e-cigaretta / vape": r"e-cigaret|elektromos cigaret|vape|gőzöl",
    "nikotinpárna / snus": r"nikotinpárna|snus|snüsz|nikotin tasak",
    "ízesített termék": r"ízesít|aroma|mentol",
    "hagyományos cigaretta": r"hagyományos cigaret|cigaretta|dohányáru",
}
# D3 — iparági "aláírás-állítások": specifikus, visszakövethető érvpanelek
D3_ALAIRAS = {
    "95%-os / kevésbé káros állítás": r"95\s?%|kevésbé (káros|ártalmas)|ártalomcsökkent",
    "svéd modell / Svédország": r"svéd(ország)?(i)? (modell|példa|tapasztalat)|svédország",
    "a tilalom nem működik / prohibíció": r"a tilalom nem (működik|old)|tiltás nem (működik|old)|prohibíció|betiltás nem (vezet|old)",
    "feketepiaci átterelődés": r"feketepiac|fekete piac|csempész|illegális (piac|beszerz)",
    "leszokás eszköze": r"leszokásban segít|segített leszokni|leszokás(t|ban|hoz) (segít|támogat|eszköz)|kilépő út|áttérni segít|le tudtam szokni",
    "ártalmatlanság-állítás": r"nem (káros|ártalmas|okoz rákot|okoz betegséget)|ártalmatlan|semmilyen egészségügyi kockázat",
    "munkahely-veszteség": r"munkahely (veszély|megszűn|elveszt)|elbocsát|munkanélküli",
}
# D4 — hazai szabályozási keret (a hazai kontextusra fordított uniós vita)
D4_HAZAI = r"trafik|nemzeti dohánybolt|koncesszió|jövedéki adó|magyar (kormány|szabályoz|piac)|magyarországon"
# D6 — regiszter
D6_SZEMELYES = r"\b(én|nekem|nálam|számomra|saját tapasztalat|családom|a férjem|a feleségem|a munkahelyem)\b"
D6_ESSZE = r"^(az európai unió|a dohányzás|a szabályozás|a javasolt|kulcsfontosságú|fontos(,| ) hogy|a dohánytermék)"

for nev, pat in D1_ESZKOZ.items():
    df[f"D1: {nev}"] = df["t"].str.contains(nc(pat), regex=True)
for nev, pat in D3_ALAIRAS.items():
    df[f"D3: {nev}"] = df["t"].str.contains(nc(pat), regex=True)

df["D4 hazai keret"] = df["t"].str.contains(nc(D4_HAZAI), regex=True)
df["D5 ifjúságvédelem-appropriáció"] = (
    df["t"].str.contains(nc(EU_ERV["H1 ifjúságvédelem"]), regex=True) & df["pozicio"].eq(ELLENE))
df["D6 személyes regiszter"] = df["t"].str.contains(nc(D6_SZEMELYES), regex=True)
df["D6 személytelen esszé"] = df["t"].str.contains(nc(D6_ESSZE), regex=True)


def vedett_termek(sor):
    """D2: melyik termékkategóriát védi — csak szigorítás-ellenes szövegben értelmes."""
    if sor["pozicio"] != ELLENE:
        return "-"
    talalat = [n for n, p in D2_TERMEK.items() if re.search(nc(p), sor["t"])]
    return "|".join(talalat) if talalat else "nincs konkrét termék"


df["D2 védett termék"] = df.apply(vedett_termek, axis=1)

# ═══════════════════════════════════════════════════════════════ 5. RIPORT
N = len(df)
V = "═" * 74


def tabla(s, cim, sorrend=None):
    t = s.value_counts()
    if sorrend:
        t = t.reindex(sorrend).fillna(0).astype(int)
    t = t.to_frame("db")
    t["%"] = (t["db"] / N * 100).round(2)
    print(f"\n{cim}\n{t.to_string()}")
    return t


print(f"\n{V}\nMAGYAR NYELVŰ HOZZÁSZÓLÁSOK — n = {N:,}\n{V}")

t_cs = tabla(df["csoport"], "1) KI HALLATJA A HANGJÁT? (szigorú önazonosítás)", [C1, C2, C3, C4, C5])
print(f"\n   A 3. csoporton (természetes személy) belül:")
c3 = df[df.csoport.eq(C3)]
print(f"     önazonosított fogyasztó (dohányzom/leszoktam/gőzölök): {int(c3.fogyasztoi_onazonositas.sum()):,}"
      f" ({c3.fogyasztoi_onazonositas.mean():.1%})")
print(f"     iparági érvelésű (≥2 érvcsalád, iparági dominancia)   : "
      f"{int(((c3.n_ipar >= 2) & (c3.n_ipar > c3.n_eu)).sum()):,}")
print(f"     rövid, indoklás nélküli (≤10 szó)                     : {int(c3.szoszam.le(10).sum()):,}")
print(f"\n   Besorolás alapja: " + " / ".join(
    f"{k}: {v:,}" for k, v in df["evidencia"].value_counts().items()))

t_poz = tabla(df["pozicio"], "2) MIT KÉPVISELNEK?", [MELLETTE, ELLENE, DIFF, VEGYES, NINCS])
mel, ell = int(df.pozicio.eq(MELLETTE).sum()), int(df.pozicio.eq(ELLENE).sum())
print(f"\n   ELLENE / MELLETTE arány: {ell/max(mel,1):.1f} : 1")

print("\n3) CSOPORT × POZÍCIÓ (db)")
kereszt = pd.crosstab(df["csoport"], df["pozicio"]).reindex(
    index=[C1, C2, C3, C4, C5], columns=[MELLETTE, ELLENE, DIFF, VEGYES, NINCS]).fillna(0).astype(int)
print(kereszt.to_string())

print(f"\n{V}\nD1) MELYIK SZABÁLYOZÁSI ESZKÖZ JELENIK MEG (többszörös besorolás)\n{V}")
d1 = pd.DataFrame({
    "összes db": [int(df[f"D1: {n}"].sum()) for n in D1_ESZKOZ],
    "%": [round(df[f"D1: {n}"].mean() * 100, 1) for n in D1_ESZKOZ],
    "ebből ELLENE": [int((df[f"D1: {n}"] & df.pozicio.eq(ELLENE)).sum()) for n in D1_ESZKOZ],
    "ebből MELLETTE": [int((df[f"D1: {n}"] & df.pozicio.eq(MELLETTE)).sum()) for n in D1_ESZKOZ],
}, index=list(D1_ESZKOZ)).sort_values("összes db", ascending=False)
print(d1.to_string())

print(f"\n{V}\nD2) MELYIK TERMÉKKATEGÓRIÁT VÉDIK (csak a szigorítás-ellenes szövegekben)\n{V}")
d2 = (df.loc[df.pozicio.eq(ELLENE), "D2 védett termék"].str.split("|").explode()
      .value_counts().to_frame("db"))
d2["%"] = (d2["db"] / max(ell, 1) * 100).round(1)
print(d2.to_string())

print(f"\n{V}\nD3) IPARÁGI ALÁÍRÁS-ÁLLÍTÁSOK\n{V}")
d3 = pd.DataFrame({
    "db": [int(df[f"D3: {n}"].sum()) for n in D3_ALAIRAS],
    "%": [round(df[f"D3: {n}"].mean() * 100, 1) for n in D3_ALAIRAS],
}, index=list(D3_ALAIRAS)).sort_values("db", ascending=False)
print(d3.to_string())
d3_cols = [f"D3: {n}" for n in D3_ALAIRAS]
df["n_alairas"] = df[d3_cols].sum(axis=1)
print(f"\n   Hány aláírás-állítást mozgat egy hozzászólás (átlag): {df.n_alairas.mean():.2f}")
print(f"   Legalább 3 aláírás-állítást tartalmaz: {int(df.n_alairas.ge(3).sum()):,} "
      f"({df.n_alairas.ge(3).mean():.1%})")

print(f"\n{V}\nD4–D6) KONTEXTUS ÉS REGISZTER\n{V}")
print(f"Hazai szabályozási keretet említ (trafik/koncesszió/jövedéki adó): "
      f"{int(df['D4 hazai keret'].sum()):,} ({df['D4 hazai keret'].mean():.1%})")
print(f"Ifjúságvédelmi érv a szigorítás ELLEN (appropriáció)             : "
      f"{int(df['D5 ifjúságvédelem-appropriáció'].sum()):,} ({df['D5 ifjúságvédelem-appropriáció'].mean():.1%})")
print(f"Személyes regiszter (E/1, saját tapasztalat)                     : "
      f"{int(df['D6 személyes regiszter'].sum()):,} ({df['D6 személyes regiszter'].mean():.1%})")
print(f"Személytelen szakpolitikai esszé (így kezdődik)                  : "
      f"{int(df['D6 személytelen esszé'].sum()):,} ({df['D6 személytelen esszé'].mean():.1%})")
print(f"Medián szószám: {df.szoszam.median():.0f} | 81+ szavas: {df.szoszam.ge(81).mean():.1%}")

print(f"\n{V}\nD7) IDŐBELI MOBILIZÁCIÓ — 10 legnagyobb beadási nap\n{V}")
napi = df.groupby(df.datum.dt.date).size().sort_values(ascending=False)
print(napi.head(10).to_frame("db").to_string())
print(f"\n   A 3 legnagyobb nap a magyar hozzászólások {napi.head(3).sum()/N:.1%}-át adja.")

# ═══════════════════════════════ 6. PONTOSSÁG-ELLENŐRZŐ MINTA (kézi validálás)
print(f"\n{V}\nPONTOSSÁG-ELLENŐRZÉS — csoportonként 5 véletlen találat és a bizonyíték\n{V}")
for cs in [C1, C2, C4, C5]:
    minta = df[df.csoport.eq(cs) & df.evidencia.eq("önazonosítás")]
    print(f"\n--- {cs}  (önazonosítás alapján: {len(minta):,}) ---")
    for _, s in minta.sample(min(5, len(minta)), random_state=42).iterrows():
        print(f"   • {s['bizonyitek'][:150]}")

# ═══════════════════════════════════════════════════════════════ 7. EXPORT
xlsx, csv = f"{KIM}/HU_elemzes_v4.xlsx", f"{KIM}/HU_kodolt_v4.csv"
with pd.ExcelWriter(xlsx, engine="openpyxl") as w:
    t_cs.to_excel(w, sheet_name="csoport")
    t_poz.to_excel(w, sheet_name="pozicio")
    kereszt.to_excel(w, sheet_name="csoport_x_pozicio")
    d1.to_excel(w, sheet_name="D1_szabalyozasi_eszkoz")
    d2.to_excel(w, sheet_name="D2_vedett_termek")
    d3.to_excel(w, sheet_name="D3_alairas_allitasok")
    napi.to_frame("db").to_excel(w, sheet_name="D7_napi")

exp = ["id", "dateFeedback", "country", "userType", "organization", "szoszam", "csoport",
       "evidencia", "bizonyitek", "osszes_szerep", "fogyasztoi_onazonositas", "n_ipar", "n_eu",
       "pozicio", "pozicio_szint", "D2 védett termék", "D4 hazai keret",
       "D5 ifjúságvédelem-appropriáció", "D6 személyes regiszter", "D6 személytelen esszé",
       "n_alairas"] + [f"D1: {n}" for n in D1_ESZKOZ] + d3_cols + ["feedback"]
df[exp].to_csv(csv, index=False, encoding="utf-8-sig")
print(f"\n[OK] {xlsx}\n[OK] {csv}")
