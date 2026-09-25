"""Logique de preremplissage XFA (IRCC). Utilisee par api/fill.py (Vercel) et server.py (Docker)."""
import os, io
TPL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")

FORMS = {
    "IMM 1294": {
        "template": "imm1294f.pdf", "filename": "IMM1294_prerempli.pdf",
        "map": {
            "nom": "form1/Page1/PersonalDetails/Name/FamilyName",
            "prenom": "form1/Page1/PersonalDetails/Name/GivenName",
            "lieu_naissance": "form1/Page1/PersonalDetails/PlaceBirthCity",
            "pays_citoyennete": "form1/Page1/PersonalDetails/PlaceBirthCountry",
            "passeport_numero": "form1/Page2/MaritalStatus/SectionA/Passport/PassportNum/PassportNum",
            "passeport_expiration": "form1/Page2/MaritalStatus/SectionA/Passport/ExpiryDate",
            "passeport_emission": "form1/Page2/MaritalStatus/SectionA/Passport/IssueDate/IssueDate",
            "_dob": ("form1/Page1/PersonalDetails/DOBYear",
                     "form1/Page1/PersonalDetails/DOBMonth",
                     "form1/Page1/PersonalDetails/DOBDay"),
        },
    },
    # Ajouter IMM 5257 / IMM 5645 : deposer le gabarit dans templates/ et mapper les chemins ici.
}
ALIASES = {"imm1294": "IMM 1294", "imm 1294": "IMM 1294",
           "permis d'etudes": "IMM 1294", "permis d'études": "IMM 1294"}

def resolve_form(name):
    n = (name or "").strip()
    if n in FORMS: return n
    low = n.lower()
    for k in FORMS:
        if k.lower() in low or low in k.lower(): return k
    return ALIASES.get(low)

def fill(form_key, dossier):
    import pikepdf
    from lxml import etree
    cfg = FORMS[form_key]
    pdf = pikepdf.open(os.path.join(TPL_DIR, cfg["template"]))
    arr = list(pdf.Root.AcroForm.XFA)
    di = [i+1 for i in range(0, len(arr), 2) if str(arr[i]) == "datasets"][0]
    root = etree.fromstring(bytes(arr[di].read_bytes()))
    form1 = [c for c in root.iter() if etree.QName(c).localname == "form1"][0]
    def node(path):
        cur = form1
        for name in path.split("/")[1:]:
            nxt = None
            for c in cur:
                if etree.QName(c).localname == name: nxt = c; break
            if nxt is None: return None
            cur = nxt
        return cur
    remplis = []
    for key, path in cfg["map"].items():
        if key == "_dob":
            dob = (dossier.get("date_naissance") or "").split("-")
            if len(dob) == 3:
                for p, v in zip(path, dob):
                    n = node(p)
                    if n is not None: n.text = v; remplis.append(p.split("/")[-1])
            continue
        val = dossier.get(key)
        if val is None or str(val).strip() == "": continue
        n = node(path)
        if n is not None: n.text = str(val); remplis.append(path.split("/")[-1])
    arr[di].write(etree.tostring(root, encoding="UTF-8"))
    buf = io.BytesIO(); pdf.save(buf)
    return buf.getvalue(), remplis, cfg["filename"]
