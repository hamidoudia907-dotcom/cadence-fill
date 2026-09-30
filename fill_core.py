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
import os, io, re
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
            "etat_matrimonial": "form1/Page1/MaritalStatus/SectionA/MaritalStatus",
            "telephone": "form1/Page2/contact/PhoneNumbers/Phone/IntlNumber/IntlNumber",
            "meme_adresse": "form1/Page2/contact/SameAsMailingIndicator",
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
            "pays_residence": "form1/Page1/PersonalDetails/CurrentCOR/Row2/Pays",
            "courriel": "form1/Page2/ContactInformation/contact/FaxEmail/Email",
            "adresse_rue": "form1/Page2/ContactInformation/contact/AddressRow1/Streetname/Streetname",
            "adresse_ville": "form1/Page2/ContactInformation/contact/AddressRow2/CityTow/CityTown",
            "adresse_pays": "form1/Page2/ContactInformation/contact/AddressRow2/Pays/Pays",
            "adresse_province": "form1/Page2/ContactInformation/contact/AddressRow2/ProvinceState/ProvinceState",
            "adresse_code_postal": "form1/Page2/ContactInformation/contact/AddressRow2/PostalCode/PostalCode",
            "etat_matrimonial": "form1/Page1/MaritalStatus/SectionA/MaritalStatus",
            "telephone": "form1/Page2/ContactInformation/contact/PhoneNumbers/Phone/IntlNumber/IntlNumber",
            "meme_adresse": "form1/Page2/ContactInformation/contact/SameAsMailingIndicator",
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
            "pays_residence": "form1/Page1/PersonalDetails/CurrentCOR/CurrentCOR/Row2/Country",
            "courriel": "form1/Page2/ContactInformation/q5-6/Email/Email",
            "adresse_rue": "form1/Page2/ContactInformation/Mailing/AddrLine1/Streetname",
            "adresse_ville": "form1/Page2/ContactInformation/Mailing/AddrLine2/City",
            "adresse_pays": "form1/Page2/ContactInformation/Mailing/AddrLine2/Country",
            "adresse_province": "form1/Page2/ContactInformation/Mailing/AddrLine2/Prov",
            "adresse_code_postal": "form1/Page2/ContactInformation/Mailing/AddrLine2/PostalCode",
            "etat_matrimonial": "form1/Page1/MaritalStatus/Current/MaritalStatus",
            "telephone": "form1/Page2/ContactInformation/q3-4/Phone/IntlNumber/IntlNumber",
            "meme_adresse": "form1/Page2/ContactInformation/Resi/SameAsAddr/SameAsMailingInd",
            "passeport_numero": "form1/Page2/Passport/PassportNum",
            "passeport_pays": "form1/Page2/Passport/CountryofIssue",
            "passeport_emission": "form1/Page2/Passport/IssueDate",
            "passeport_expiration": "form1/Page2/Passport/ExpiryDate",
            "_dob": ("form1/Page1/PersonalDetails/q3-4-5/dob/DOBYear",
                     "form1/Page1/PersonalDetails/q3-4-5/dob/DOBMonth",
                     "form1/Page1/PersonalDetails/q3-4-5/dob/DOBDay"),
        },
    },
    "IMM 1295": {  # Demande de permis de travail (hors Canada)
        "template": "imm1295e.pdf", "filename": "IMM1295_prerempli.pdf",
        "map": {
            "nom": "form1/Page1/PersonalDetails/Name/FamilyName",
            "prenom": "form1/Page1/PersonalDetails/Name/GivenName",
            "sexe": "form1/Page1/PersonalDetails/Sex/Sex",
            "lieu_naissance": "form1/Page1/PersonalDetails/PlaceBirthCity",
            "pays_naissance": "form1/Page1/PersonalDetails/PlaceBirthCountry",
            "pays_citoyennete": "form1/Page1/PersonalDetails/Citizenship/Citizenship",
            "pays_residence": "form1/Page1/PersonalDetails/CurrentCOR/Row2/Country",
            "courriel": "form1/Page3/FaxEmail/Email",
            "adresse_rue": "form1/Page2/ContactInformation/contact/AddressRow1/Streetname/Streetname",
            "adresse_ville": "form1/Page2/ContactInformation/contact/AddressRow2/CityTow/CityTown",
            "adresse_province": "form1/Page2/ContactInformation/contact/AddressRow2/ProvinceState/ProvinceState",
            "adresse_code_postal": "form1/Page2/ContactInformation/contact/AddressRow2/PostalCode/PostalCode",
            "etat_matrimonial": "form1/Page1/MaritalStatus/SectionA/MaritalStatus",
            "telephone": "form1/Page2/ContactInformation/contact/PhoneNumbers/Phone/IntlNumber/IntlNumber",
            "meme_adresse": "form1/Page2/ContactInformation/contact/SameAsMailingIndicator",
            "passeport_numero": "form1/Page2/MaritalStatus/SectionA/Passport/PassportNum/PassportNum",
            "passeport_pays": "form1/Page2/MaritalStatus/SectionA/Passport/CountryofIssue/CountryofIssue",
            "passeport_emission": "form1/Page2/MaritalStatus/SectionA/Passport/IssueDate/IssueDate",
            "passeport_expiration": "form1/Page2/MaritalStatus/SectionA/Passport/ExpiryDate",
            "_dob": ("form1/Page1/PersonalDetails/DOBYear",
                     "form1/Page1/PersonalDetails/DOBMonth",
                     "form1/Page1/PersonalDetails/DOBDay"),
        },
    },
    "IMM 5710": {  # Prolongation/modification permis de travail (au Canada)
        "template": "imm5710e.pdf", "filename": "IMM5710_prerempli.pdf",
        "map": {
            "nom": "form1/Page1/PersonalDetails/Name/FamilyName",
            "prenom": "form1/Page1/PersonalDetails/Name/GivenName",
            "sexe": "form1/Page1/PersonalDetails/q3-4-5/sex/Sex",
            "lieu_naissance": "form1/Page1/PersonalDetails/q3-4-5/pob/PlaceBirthCity",
            "pays_naissance": "form1/Page1/PersonalDetails/q3-4-5/pob/PlaceBirthCountry",
            "pays_citoyennete": "form1/Page1/PersonalDetails/Citizenship/Citizenship",
            "pays_residence": "form1/Page1/PersonalDetails/CurrentCOR/CurrentCOR/Row2/Country",
            "courriel": "form1/Page2/ContactInformation/q5-6/Email/Email",
            "adresse_rue": "form1/Page2/ContactInformation/Mailing/AddrLine1/Streetname",
            "adresse_ville": "form1/Page2/ContactInformation/Mailing/AddrLine2/City",
            "adresse_pays": "form1/Page2/ContactInformation/Mailing/AddrLine2/Country",
            "adresse_province": "form1/Page2/ContactInformation/Mailing/AddrLine2/Prov",
            "adresse_code_postal": "form1/Page2/ContactInformation/Mailing/AddrLine2/PostalCode",
            "etat_matrimonial": "form1/Page1/MaritalStatus/Current/MaritalStatus",
            "telephone": "form1/Page2/ContactInformation/q3-4/Phone/IntlNumber/IntlNumber",
            "meme_adresse": "form1/Page2/ContactInformation/Resi/SameAsAddr/SameAsMailingInd",
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

# Historique scolaire / professionnel (1 ligne d'etudes + 3 lignes d'emploi,
# limite reelle des formulaires IRCC). Sous-cles d'une entree :
#   etudes  : ecole, domaine, ville, pays, province, du (AAAA-MM), au (AAAA-MM)
#   emplois : poste, employeur, ville, pays, province, du (AAAA-MM), au (AAAA-MM)
def _occ_1294(i):
    b = "form1/Page3/Occupation/OccupationRow%d" % i
    return {"poste": b + "/Occupation/Occupation", "employeur": b + "/Employer",
            "ville": b + "/CityTown/CityTown", "pays": b + "/Pays/Pays", "province": b + "/ProvState",
            "du_year": b + "/FromYear", "du_month": b + "/FromMonth",
            "au_year": b + "/ToYear", "au_month": b + "/ToMonth"}

_EDU_1294 = {
    "ecole": "form1/Page3/Education/Edu_Row1/School",
    "domaine": "form1/Page3/Education/Edu_Row1/FieldOfStudy",
    "ville": "form1/Page3/Education/Edu_Row1/CityTown",
    "pays": "form1/Page3/Education/Edu_Row1/Pays/Pays",
    "province": "form1/Page3/Education/Edu_Row1/ProvState",
    "du_year": "form1/Page3/Education/Edu_Row1/FromYear",
    "du_month": "form1/Page3/Education/Edu_Row1/FromMonth",
    "au_year": "form1/Page3/Education/Edu_Row1/ToYear",
    "au_month": "form1/Page3/Education/Edu_Row1/ToMonth",
}

def _emp_5709(i):
    b = "form1/Page3/Employment/EmpRec%d" % i
    return {"poste": b + "/Line1/Occupation", "employeur": b + "/Line1/Employer",
            "du_year": b + "/Line1/From/YYYY", "du_month": b + "/Line1/From/MM",
            "ville": b + "/Line2/City", "pays": b + "/Line2/Country", "province": b + "/Line2/ProvState",
            "au_year": b + "/Line2/To/YYYY", "au_month": b + "/Line2/To/MM"}

_EDU_5709 = {
    "ecole": "form1/Page3/Education/EduLine1/School",
    "domaine": "form1/Page3/Education/EduLine1/FieldOfStudy",
    "du_year": "form1/Page3/Education/EduLine1/From/YYYY",
    "du_month": "form1/Page3/Education/EduLine1/From/MM",
    "ville": "form1/Page3/Education/EduLine2/City",
    "pays": "form1/Page3/Education/EduLine2/Country",
    "province": "form1/Page3/Education/EduLine2/Prov",
    "au_year": "form1/Page3/Education/EduLine2/To/YYYY",
    "au_month": "form1/Page3/Education/EduLine2/To/MM",
}

def _occ_1295(i):
    b = "form1/Page3/PageWrapper/Occupation/OccupationRow%d" % i
    return {"poste": b + "/Occupation/Occupation", "employeur": b + "/Employer",
            "ville": b + "/CityTown/CityTown", "pays": b + "/Country/Country", "province": b + "/ProvState",
            "du_year": b + "/FromYear", "du_month": b + "/FromMonth",
            "au_year": b + "/ToYear", "au_month": b + "/ToMonth"}

_EDU_1295 = {
    "ecole": "form1/Page3/PageWrapper/Education/Edu_Row1/School",
    "domaine": "form1/Page3/PageWrapper/Education/Edu_Row1/FieldOfStudy",
    "ville": "form1/Page3/PageWrapper/Education/Edu_Row1/CityTown",
    "pays": "form1/Page3/PageWrapper/Education/Edu_Row1/Country/Country",
    "province": "form1/Page3/PageWrapper/Education/Edu_Row1/ProvState",
    "du_year": "form1/Page3/PageWrapper/Education/Edu_Row1/FromYear",
    "du_month": "form1/Page3/PageWrapper/Education/Edu_Row1/FromMonth",
    "au_year": "form1/Page3/PageWrapper/Education/Edu_Row1/ToYear",
    "au_month": "form1/Page3/PageWrapper/Education/Edu_Row1/ToMonth",
}

def _emp_5710(base):
    return {"poste": base + "/Line1/Occupation", "employeur": base + "/Line1/Employer",
            "du_year": base + "/Line1/From/YYYY", "du_month": base + "/Line1/From/MM",
            "ville": base + "/Line2/City", "pays": base + "/Line2/Country", "province": base + "/Line2/ProvState",
            "au_year": base + "/Line2/To/YYYY", "au_month": base + "/Line2/To/MM"}

_EDU_5710 = {
    "ecole": "form1/Page3/Education/EduLine1/School",
    "domaine": "form1/Page3/Education/EduLine1/FieldOfStudy",
    "du_year": "form1/Page3/Education/EduLine1/From/YYYY",
    "du_month": "form1/Page3/Education/EduLine1/From/MM",
    "ville": "form1/Page3/Education/EduLine2/City",
    "pays": "form1/Page3/Education/EduLine2/Country",
    "province": "form1/Page3/Education/EduLine2/Prov",
    "au_year": "form1/Page3/Education/EduLine2/To/YYYY",
    "au_month": "form1/Page3/Education/EduLine2/To/MM",
}

HISTORIQUE = {
    "IMM 1294": {"education": _EDU_1294, "employment": [_occ_1294(1), _occ_1294(2), _occ_1294(3)]},
    "IMM 5257": {"education": _EDU_1294, "employment": [_occ_1294(1), _occ_1294(2), _occ_1294(3)]},
    "IMM 5709": {"education": _EDU_5709, "employment": [
        _emp_5709(1), _emp_5709(2),
        {"poste": "form1/Page4/EmpRec3/Line1/Occupation", "employeur": "form1/Page4/EmpRec3/Line1/Employer"},
    ]},
    "IMM 1295": {"education": _EDU_1295, "employment": [_occ_1295(1), _occ_1295(2), _occ_1295(3)]},
    "IMM 5710": {"education": _EDU_5710, "employment": [
        _emp_5710("form1/Page3/Employment/EmpRec1"),
        _emp_5710("form1/Page4/EmpRec2"),
        _emp_5710("form1/Page4/EmpRec3"),
    ]},
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
    if not n: return None  # avant : une valeur vide renvoyait IMM 1294 par defaut
    if n in FORMS: return n
    low = n.lower()
    compact = low.replace(" ", "")
    for k in FORMS:
        if k.lower() in low or k.lower().replace(" ", "") == compact: return k
    return ALIASES.get(low)

# Gabarits non inclus dans le depot : telecharges depuis la source officielle
# (IRCC) au premier usage puis mis en cache. Le serveur d'execution doit avoir
# acces a canada.ca.
TEMPLATE_URLS = {
    "imm1295e.pdf": "https://www.canada.ca/content/dam/ircc/documents/pdf/english/kits/forms/imm1295/01-09-2023/imm1295e.pdf",
    "imm5710e.pdf": "https://www.canada.ca/content/dam/ircc/documents/pdf/english/kits/forms/imm5710/01-09-2023/imm5710e.pdf",
}

def _find_template(cfg):
    import glob
    stem = os.path.splitext(cfg["template"])[0].rstrip("f")
    for dd in (TPL_DIR, os.path.dirname(os.path.abspath(__file__))):
        exact = os.path.join(dd, cfg["template"])
        if os.path.exists(exact): return exact
        cands = sorted(glob.glob(os.path.join(dd, "*" + stem + "*.pdf")))
        if cands: return cands[0]
    url = TEMPLATE_URLS.get(cfg["template"])
    if url:
        cache = os.path.join("/tmp", cfg["template"])
        if os.path.exists(cache) and os.path.getsize(cache) > 10000:
            return cache
        import urllib.request
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = r.read()
        with open(cache, "wb") as fh:
            fh.write(data)
        return cache
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

    # Historique scolaire et professionnel (1 etude + jusqu'a 3 emplois).
    hist = HISTORIQUE.get(form_key)
    if hist:
        def _split_ym(v):
            v = (str(v) if v is not None else "").strip()
            if not v:
                return ("", "")
            parts = re.split(r"[-/]", v)
            if len(parts) >= 2:
                return (parts[0].strip(), parts[1].strip().zfill(2))
            return (v, "")

        def _fill_entry(src, mp):
            dy, dm = _split_ym(src.get("du"))
            ay, am = _split_ym(src.get("au"))
            derived = {"du_year": dy, "du_month": dm, "au_year": ay, "au_month": am}
            for sk, path in mp.items():
                val = derived[sk] if sk in derived else src.get(sk)
                if val is None or str(val).strip() == "":
                    continue
                n = node(path)
                if n is not None:
                    n.text = str(val); remplis.append(path.split("/")[-1])

        etudes = dossier.get("etudes") or []
        if etudes and hist.get("education"):
            _fill_entry(etudes[0], hist["education"])
        emplois = dossier.get("emplois") or []
        emp_maps = hist.get("employment") or []
        for i, emp in enumerate(emplois[:len(emp_maps)]):
            _fill_entry(emp, emp_maps[i])

    arr[di].write(etree.tostring(root, encoding="UTF-8"))
    buf = io.BytesIO(); pdf.save(buf)
    return buf.getvalue(), remplis, cfg["filename"]
