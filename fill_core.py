"""Logique de preremplissage XFA (IRCC). Utilisee par api/fill.py (Vercel) et server.py (Docker).

Approche : les formulaires IRCC sont des PDF dynamiques XFA (Adobe LiveCycle).
On injecte les valeurs dans le paquet 'datasets' du XFA. Le code-barres 2D
n'est PAS regenere ici : l'avocat ouvre le PDF prerempli dans Adobe Reader,
verifie, clique Valider (le code-barres se met a jour) puis signe.

Trois formulaires ne passent pas par cette methode :
  - IMM 0008  : paquet datasets vide (dataGroup), la structure n'existe pas -> non gere
  - IMM 5669  : aucun paquet datasets dans le XFA -> non gere
  - IMM 5690  : liste de controle (cases a cocher seulement), rien a preremplir
"""
import os, io
TPL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")

# Chaque map : cle_dossier -> chemin XFA (depuis la racine des donnees).
# "_dob" (optionnel) -> (chemin_annee, chemin_mois, chemin_jour) pour les
# formulaires ou la date de naissance est eclatee en trois champs.
FORMS = {
    "IMM 1294": {  # Demande de permis d'etudes
        "template": "imm1294f.pdf", "filename": "IMM1294_prerempli.pdf",
        "map": {
            "nom": "form1/Page1/PersonalDetails/Name/FamilyName",
            "prenom": "form1/Page1/PersonalDetails/Name/GivenName",
            "sexe": "form1/Page1/PersonalDetails/Sex/Sex",
            "lieu_naissance": "form1/Page1/PersonalDetails/PlaceBirthCity",
            "pays_naissance": "form1/Page1/PersonalDetails/PlaceBirthCountry",
            "pays_citoyennete": "form1/Page1/PersonalDetails/Citizenship/Citizenship",
            "pays_residence": "form1/Page1/PersonalDetails/CurrentCOR/Row2/Pays",
            "courriel": "form1/Page2/contact/FaxEmail/Email",
            "adresse_rue": "form1/Page2/contact/AddressRow1/Streetname/Streetname",
            "adresse_ville": "form1/Page2/contact/AddressRow2/CityTow/CityTown",
            "adresse_pays": "form1/Page2/contact/AddressRow2/Pays/Pays",
            "adresse_province": "form1/Page2/contact/AddressRow2/ProvinceState/ProvinceState",
            "adresse_code_postal": "form1/Page2/contact/AddressRow2/PostalCode/PostalCode",
            "passeport_numero": "form1/Page2/MaritalStatus/SectionA/Passport/PassportNum/PassportNum",
            "passeport_pays": "form1/Page2/MaritalStatus/SectionA/Passport/CountryofIssue/CountryofIssue",
            "passeport_emission": "form1/Page2/MaritalStatus/SectionA/Passport/IssueDate/IssueDate",
            "passeport_expiration": "form1/Page2/MaritalStatus/SectionA/Passport/ExpiryDate",
            "_dob": ("form1/Page1/PersonalDetails/DOBYear",
                     "form1/Page1/PersonalDetails/DOBMonth",
                     "form1/Page1/PersonalDetails/DOBDay"),
        },
    },
    "IMM 5257": {  # Demande de visa de residence temporaire (visiteur)
        "template": "imm5257f.pdf", "filename": "IMM5257_prerempli.pdf",
        "map": {
            "nom": "form1/Page1/PersonalDetails/Name/FamilyName",
            "prenom": "form1/Page1/PersonalDetails/Name/GivenName",
            "sexe": "form1/Page1/PersonalDetails/Sex/Sex",
            "lieu_naissance": "form1/Page1/PersonalDetails/PlaceBirthCity",
            "pays_naissance": "form1/Page1/PersonalDetails/PlaceBirthCountry",
            "pays_citoyennete": "form1/Page1/PersonalDetails/Citizenship/Citizenship",
            "courriel": "form1/Page2/ContactInformation/contact/FaxEmail/Email",
            "passeport_numero": "form1/Page2/MaritalStatus/SectionA/Passport/PassportNum/PassportNum",
            "passeport_pays": "form1/Page2/MaritalStatus/SectionA/Passport/CountryofIssue/CountryofIssue",
            "passeport_emission": "form1/Page2/MaritalStatus/SectionA/Passport/IssueDate/IssueDate",
            "passeport_expiration": "form1/Page2/MaritalStatus/SectionA/Passport/ExpiryDate",
            "_dob": ("form1/Page1/PersonalDetails/DOBYear",
                     "form1/Page1/PersonalDetails/DOBMonth",
                     "form1/Page1/PersonalDetails/DOBDay"),
        },
    },
    "IMM 5709": {  # Demande de prolongation/modification de statut (etudes)
        "template": "imm5709e.pdf", "filename": "IMM5709_prerempli.pdf",
        "map": {
            "nom": "form1/Page1/PersonalDetails/Name/FamilyName",
            "prenom": "form1/Page1/PersonalDetails/Name/GivenName",
            "sexe": "form1/Page1/PersonalDetails/q3-4-5/sex/Sex",
            "lieu_naissance": "form1/Page1/PersonalDetails/q3-4-5/pob/PlaceBirthCity",
            "pays_naissance": "form1/Page1/PersonalDetails/q3-4-5/pob/PlaceBirthCountry",
            "pays_citoyennete": "form1/Page1/PersonalDetails/Citizenship/Citizenship",
            "courriel": "form1/Page2/ContactInformation/q5-6/Email/Email",
            "passeport_numero": "form1/Page2/Passport/PassportNum",
            "passeport_pays": "form1/Page2/Passport/CountryofIssue",
            "passeport_emission": "form1/Page2/Passport/IssueDate",
            "passeport_expiration": "form1/Page2/Passport/ExpiryDate",
            "_dob": ("form1/Page1/PersonalDetails/q3-4-5/dob/DOBYear",
                     "form1/Page1/PersonalDetails/q3-4-5/dob/DOBMonth",
                     "form1/Page1/PersonalDetails/q3-4-5/dob/DOBDay"),
        },
    },
    "IMM 5645": {  # Renseignements sur la famille (date de naissance = champ unique)
        "template": "imm5645f.pdf", "filename": "IMM5645_prerempli.pdf",
        "map": {
            "nom_complet": "IMM_5645/page1/SectionA/Applicant/AppName",
            "date_naissance": "IMM_5645/page1/SectionA/Applicant/AppDOB",
            "conjoint_nom": "IMM_5645/page1/SectionA/Spouse/SpouseName",
            "conjoint_date_naissance": "IMM_5645/page1/SectionA/Spouse/SpouseDOB",
            "mere_nom": "IMM_5645/page1/SectionA/Mother/MotherName",
            "mere_date_naissance": "IMM_5645/page1/SectionA/Mother/MotherDOB",
            "pere_nom": "IMM_5645/page1/SectionA/Father/FatherName",
            "pere_date_naissance": "IMM_5645/page1/SectionA/Father/FatherDOB",
        },
    },
    "IMM 5406": {  # Renseignements additionnels sur la famille (date de naissance = champ unique)
        "template": "imm5406f.pdf", "filename": "IMM5406_prerempli.pdf",
        "map": {
            "nom": "IMM_5406/page1/SectionA/SectionAinfo/Applicant/PaddedEntry/PersonalData/Row/FamilyName",
            "prenom": "IMM_5406/page1/SectionA/SectionAinfo/Applicant/PaddedEntry/PersonalData/Row/GivenNames",
            "date_naissance": "IMM_5406/page1/SectionA/SectionAinfo/Applicant/PaddedEntry/PersonalData/Row/DOB",
            "courriel": "IMM_5406/page1/SectionA/SectionAinfo/Applicant/PaddedEntry/PersonalData/Row/Email",
        },
    },
}

# Formulaires connus mais non preremplissables par injection datasets.
NON_GERES = {
    "IMM 0008": "Le paquet de donnees XFA est vide (structure non definie). A remplir directement dans Adobe.",
    "IMM 5669": "Aucun paquet de donnees XFA (antecedents/declaration). A remplir directement dans Adobe.",
    "IMM 5690": "Liste de controle a cocher : rien a preremplir.",
}

ALIASES = {
    "imm1294": "IMM 1294", "imm 1294": "IMM 1294",
    "permis d'etudes": "IMM 1294", "permis d'études": "IMM 1294",
    "imm5257": "IMM 5257", "imm 5257": "IMM 5257", "visiteur": "IMM 5257", "visa visiteur": "IMM 5257",
    "imm5709": "IMM 5709", "imm 5709": "IMM 5709", "prolongation etudes": "IMM 5709",
    "imm5645": "IMM 5645", "imm 5645": "IMM 5645", "renseignements famille": "IMM 5645",
    "imm5406": "IMM 5406", "imm 5406": "IMM 5406",
}

def resolve_form(name):
    n = (name or "").strip()
    if n in FORMS: return n
    low = n.lower()
    for k in FORMS:
        if k.lower() in low or low in k.lower(): return k
    return ALIASES.get(low)

def _find_template(cfg):
    import glob
    stem = os.path.splitext(cfg["template"])[0].rstrip("f")
    for dd in (TPL_DIR, os.path.dirname(os.path.abspath(__file__))):
        exact = os.path.join(dd, cfg["template"])
        if os.path.exists(exact): return exact
        cands = sorted(glob.glob(os.path.join(dd, "*" + stem + "*.pdf")))
        if cands: return cands[0]
    raise FileNotFoundError("Gabarit introuvable: " + cfg["template"])

def fill(form_key, dossier):
    import pikepdf
    from lxml import etree
    cfg = FORMS[form_key]
    tpl = _find_template(cfg)
    pdf = pikepdf.open(tpl)
    arr = list(pdf.Root.AcroForm.XFA)
    di = [i + 1 for i in range(0, len(arr) - 1, 2) if str(arr[i]) == "datasets"][0]
    root = etree.fromstring(bytes(arr[di].read_bytes()))

    # Racine des donnees = premier element sous <xfa:data> (form1, IMM_5645, IMM_5406, ...).
    data_el = [c for c in root.iter() if etree.QName(c).localname == "data"][0]
    data_root = next((c for c in data_el if isinstance(c.tag, str)), None)
    if data_root is None:
        raise ValueError("Paquet de donnees XFA vide pour " + form_key)

    def node(path):
        cur = data_root  # la racine est deja le premier segment du chemin
        for name in path.split("/")[1:]:
            nxt = None
            for c in cur:
                if isinstance(c.tag, str) and etree.QName(c).localname == name:
                    nxt = c; break
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
                    if n is not None:
                        n.text = v; remplis.append(p.split("/")[-1])
            continue
        val = dossier.get(key)
        if val is None or str(val).strip() == "": continue
        n = node(path)
        if n is not None:
            n.text = str(val); remplis.append(path.split("/")[-1])

    arr[di].write(etree.tostring(root, encoding="UTF-8"))
    buf = io.BytesIO(); pdf.save(buf)
    return buf.getvalue(), remplis, cfg["filename"]
