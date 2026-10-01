"""Logique de preremplissage XFA (IRCC). Utilisee par api/fill.py (Vercel) et server.py (Docker).

Approche : les formulaires IRCC sont des PDF dynamiques XFA (Adobe LiveCycle).
On injecte les valeurs dans le paquet 'datasets' du XFA. Le code-barres 2D
n'est PAS regenere ici : l'avocat ouvre le PDF prerempli dans Adobe Reader,
verifie, clique Valider (le code-barres se met a jour) puis signe.

Cas particuliers :
  - IMM 0008  : paquet datasets vide -> la structure de donnees est creee a partir du gabarit
  - IMM 5669  : aucun paquet datasets -> un paquet est ajoute au XFA
  - IMM 5690  : liste de controle (cases a cocher seulement), rien a preremplir
Les listes deroulantes (pays, sexe, etat matrimonial...) recoivent le code IRCC
(attribut 'lic') correspondant au libelle fourni, quand il est trouve.
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
    "IMM 0008": {  # Formulaire de demande generique pour le Canada (RP, asile)
        "template": "imm0008e.pdf", "filename": "IMM0008_prerempli.pdf",
        "map": {
            "nom": "form1/Page1/PersonalDetails/q1/FamilyName",
            "prenom": "form1/Page1/PersonalDetails/q1/GivenName",
            "sexe": "form1/Page1/PersonalDetails/q3-4-5-6/Sex/Sex",
            "lieu_naissance": "form1/Page1/PersonalDetails/q7-8/PlaceBirthCity",
            "pays_naissance": "form1/Page1/PersonalDetails/q7-8/PlaceBirthCountry",
            "pays_citoyennete": "form1/Page1/PersonalDetails/q9/Citizenship1",
            "etat_matrimonial": "form1/Page1/PersonalDetails/q14/MaritalStatus/MaritalStatus",
            "adresse_rue": "form1/Page1/contactInformation/q1/AddressRow1/Streetname/Streetname",
            "adresse_ville": "form1/Page1/contactInformation/q1/AddressRow2/CityTown/CityTown",
            "adresse_pays": "form1/Page1/contactInformation/q1/AddressRow2/Country/Country",
            "adresse_province": "form1/Page1/contactInformation/q1/AddressRow2/ProvinceState/ProvinceState",
            "adresse_code_postal": "form1/Page1/contactInformation/q1/AddressRow2/PostalCode/PostalCode",
            "telephone": "form1/Page1/contactInformation/q3-4/Phone/IntlNumber/IntlNumber",
            "courriel": "form1/Page1/contactInformation/q5-6/Email",
            "passeport_numero": "form1/Page1/passport/Passport/PassportNum/PassportNum",
            "passeport_pays": "form1/Page1/passport/Passport/CountryofIssue/CountryofIssue",
            "passeport_emission": "form1/Page1/passport/Passport/IssueDate/IssueDate",
            "passeport_expiration": "form1/Page1/passport/Passport/ExpiryDate",
            "_dob": ("form1/Page1/PersonalDetails/q7-8/DOB/DOBYYYY",
                     "form1/Page1/PersonalDetails/q7-8/DOB/DOBMM",
                     "form1/Page1/PersonalDetails/q7-8/DOB/DOBDD"),
        },
    },
    "IMM 5669": {  # Annexe A - Antecedents / Declaration (pas de paquet datasets : il est cree)
        "template": "imm5669f.pdf", "filename": "IMM5669_prerempli.pdf",
        "map": {
            "nom": "IMM_5669/page1/familyName",
            "prenom": "IMM_5669/page1/givenName",
            "date_naissance": "IMM_5669/page1/birthDate3",
        },
    },
}

# Champs complementaires (statut de residence, deja marie, langues, destination, etudes, financement).
# Valeurs attendues dans le dossier :
#   statut_residence      code IRCC (ex. '01' = citoyen)
#   deja_marie            'N' ou 'Y'
#   langue_communication  'French' | 'English' | 'Both'
#   langue_correspondance '02' (francais) | '01' (anglais)   [IMM 0008]
#   langue_entrevue       '002' (francais) | '001' (anglais) [IMM 0008]
#   province_destination  abreviation (QC, ON, ...) ; ville_destination
#   etablissement, dli, frais_payes_par ('Myself'|'Parents'|'Other'), garant, fonds
_SA = "form1/Page2/MaritalStatus/SectionA"
EXTRA = {
    "IMM 1294": {
        "statut_residence": "form1/Page1/PersonalDetails/CurrentCOR/Row2/Status",
        "deja_marie": _SA + "/PrevMarriedIndicator",
        "langue_communication": _SA + "/Languages/languages/ableToCommunicate/ableToCommunicate",
        "etablissement": "form1/Page3/DetailsOfStudy/PurposeRow1/schoolName/SchoolName",
        "province_destination": "form1/Page3/DetailsOfStudy/PurposeRow1/ProvinceState/Prov",
        "ville_destination": "form1/Page3/DetailsOfStudy/PurposeRow1/CityTown/CityTown",
        "dli": "form1/Page3/DetailsOfStudy/PurposeRow1/DLI",
        "frais_payes_par": "form1/Page3/Contacts_Row1/expensesPaid/expensesPaidBy",
        "garant": "form1/Page3/Contacts_Row1/expensesPaid/Other",
        "fonds": "form1/Page3/Contacts_Row1/expensesPaid/Funds/Funds",
    },
    "IMM 5257": {
        "statut_residence": "form1/Page1/PersonalDetails/CurrentCOR/Row2/Status",
        "deja_marie": _SA + "/PrevMarriedIndicator",
        "langue_communication": _SA + "/Languages/languages/ableToCommunicate/ableToCommunicate",
        "fonds": "form1/Page3/DetailsOfVisit/PurposeRow1/Funds/Funds",
    },
    "IMM 5709": {
        "statut_residence": "form1/Page1/PersonalDetails/CurrentCOR/CurrentCOR/Row2/Status",
        "deja_marie": "form1/Page2/MaritalStatus/PrevMarriage/PrevMarriedIndicator",
        "langue_communication": "form1/Page2/Languages/communicateLang",
        "etablissement": "form1/Page3/DetailsOfStudy/SchoolDetails/SchoolName",
        "province_destination": "form1/Page3/DetailsOfStudy/SchoolDetails/Prov",
        "ville_destination": "form1/Page3/DetailsOfStudy/SchoolDetails/CityTown",
        "dli": "form1/Page3/DetailsOfStudy/SchoolDetails/DLI",
        "frais_payes_par": "form1/Page3/DetailsOfStudy/SchoolDetails/Funds/ExpPaidBy",
        "garant": "form1/Page3/DetailsOfStudy/SchoolDetails/Funds/Other",
        "fonds": "form1/Page3/DetailsOfStudy/SchoolDetails/Funds/FundsAvail",
    },
    "IMM 1295": {
        "statut_residence": "form1/Page1/PersonalDetails/CurrentCOR/Row2/Status",
        "deja_marie": _SA + "/PrevMarriedIndicator",
        "langue_communication": _SA + "/Languages/languages/ableToCommunicate/ableToCommunicate",
        "adresse_pays": "form1/Page2/ContactInformation/contact/AddressRow2/Country/Country",
        "province_destination": "form1/Page3/IntendedLocationInCanada/intendedLocation/ProvinceState/ProvinceState",
        "ville_destination": "form1/Page3/IntendedLocationInCanada/intendedLocation/CityTown/CityTown",
    },
    "IMM 5710": {
        "statut_residence": "form1/Page1/PersonalDetails/CurrentCOR/CurrentCOR/Row2/Status",
        "deja_marie": "form1/Page2/MaritalStatus/PrevMarriage/PrevMarriedIndicator",
        "langue_communication": "form1/Page2/Languages/communicateLang",
        "province_destination": "form1/Page3/DetailsOfWork/Location/Prov",
        "ville_destination": "form1/Page3/DetailsOfWork/Location/City",
    },
    "IMM 0008": {
        "pays_residence": "form1/Page1/PersonalDetails/q10/CurrentCOR/Row2/Country",
        "statut_residence": "form1/Page1/PersonalDetails/q10/CurrentCOR/Row2/Status",
        "deja_marie": "form1/Page1/PersonalDetails/q15/PrevMarriedIndicator",
        "langue_communication": "form1/Page1/languageDetails/Languages/languages/communicateLang/communicateLang",
        "langue_correspondance": ["form1/Page1/genDetails/q5/CorrespondenceLang",
                                  "form1/Page1/languageDetails/Languages/languages/freqLang"],
        "langue_entrevue": "form1/Page1/genDetails/q5/InterviewLang",
        "province_destination": "form1/Page1/genDetails/q6/Prov",
        "ville_destination": "form1/Page1/genDetails/q6/CityTown",
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
    "IMM 5690": "Liste de controle a cocher : rien a preremplir.",
}

ALIASES = {
    "imm1294": "IMM 1294", "imm 1294": "IMM 1294",
    "permis d'etudes": "IMM 1294", "permis d'études": "IMM 1294",
    "imm5257": "IMM 5257", "imm 5257": "IMM 5257", "visiteur": "IMM 5257", "visa visiteur": "IMM 5257",
    "imm5709": "IMM 5709", "imm 5709": "IMM 5709", "prolongation etudes": "IMM 5709",
    "imm5645": "IMM 5645", "imm 5645": "IMM 5645", "renseignements famille": "IMM 5645",
    "imm5406": "IMM 5406", "imm 5406": "IMM 5406",
    "imm0008": "IMM 0008", "imm 0008": "IMM 0008",
    "imm5669": "IMM 5669", "imm 5669": "IMM 5669", "annexe a": "IMM 5669",
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

XFA_DATA_NS = "http://www.xfa.org/schema/xfa-data/1.0/"

def _norm(v):
    import unicodedata
    v = unicodedata.normalize("NFD", str(v or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", v).strip()

def _template_fields(tpl_root):
    """Chemin de donnees (liaison normale) -> element <field> du gabarit."""
    from lxml import etree
    ln = lambda e: etree.QName(e).localname if isinstance(e.tag, str) else None
    out = {}
    def bind_none(e):
        return any(ln(c) == "bind" and c.get("match") == "none" for c in e)
    def walk(e, path):
        for c in e:
            t = ln(c)
            if t in ("subform", "subformSet", "area"):
                name = c.get("name")
                walk(c, path + [name] if (name and not bind_none(c)) else path)
            elif t in ("field", "exclGroup"):
                name = c.get("name")
                if name and not bind_none(c):
                    out.setdefault("/".join(path + [name]), c)
    top = next(c for c in tpl_root if ln(c) == "subform")
    walk(top, [top.get("name")])
    return out

def _lov_code(field_el, value, lov_root):
    """Convertit un libelle (ex. 'Senegal', 'M', 'Celibataire') en code de liste IRCC (attribut lic)."""
    from lxml import etree
    if field_el is None or lov_root is None: return value
    bi = next((c for c in field_el if isinstance(c.tag, str) and etree.QName(c).localname == "bindItems"), None)
    if bi is None:
        its = [c for c in field_el if isinstance(c.tag, str) and etree.QName(c).localname == "items"]
        if len(its) == 2:
            disp = [x.text or "" for x in its[0]]; save = [x.text or "" for x in its[1]]
            for d_, s_ in zip(disp, save):
                if _norm(d_) == _norm(value) or s_ == str(value).strip(): return s_
        return value
    if bi.get("valueRef") != "lic": return value
    m = re.search(r"LOV\.(\w+)\.(\w+)\[\*\]", bi.get("ref") or "")
    if not m: return value
    lst = next((e for e in lov_root.iter() if isinstance(e.tag, str) and etree.QName(e).localname == m.group(1)), None)
    if lst is None: return value
    items = [(e.get("lic") or "", e.text or "") for e in lst if isinstance(e.tag, str) and e.get("lic")]
    v = _norm(value)
    if not v: return value
    # Libelles francais -> anglais (gabarits en anglais)
    FR_EN = {"celibataire": "single", "marie": "married", "mariee": "married", "marie e": "married",
             "conjoint e de fait": "common law", "conjoint de fait": "common law", "conjointe de fait": "common law",
             "divorce": "divorced", "divorcee": "divorced", "divorce e": "divorced",
             "separe": "separated", "separee": "separated", "separe e": "separated",
             "veuf": "widowed", "veuve": "widowed", "veuf veuve": "widowed"}
    cands = [v] + ([FR_EN[v]] if v in FR_EN else [])
    for lic, lab in items:
        if _norm(lab) in cands: return lic
    for lic, lab in items:
        if lic.lower() == str(value).strip().lower(): return lic
    for lic, lab in items:
        if _norm(lab) == v: return lic
    for lic, lab in items:  # ex. 'M' -> 'M Male'
        toks = _norm(lab).split()
        if toks and (toks[0] == v or v in toks[1:2]): return lic
    for lic, lab in items:
        if _norm(lab).startswith(v + " ") or v.startswith(_norm(lab) + " "): return lic
    first = v.split()[0]
    if len(first) >= 4:  # ex. 'Veuf/Veuve' -> 'Veuf(ve)'
        for lic, lab in items:
            if _norm(lab).split()[:1] == [first]: return lic
    return value

def fill(form_key, dossier):
    import pikepdf
    from lxml import etree
    cfg = FORMS[form_key]
    tpl = _find_template(cfg)
    pdf = pikepdf.open(tpl)
    arr = list(pdf.Root.AcroForm.XFA)
    names = [str(arr[i]) for i in range(0, len(arr) - 1, 2)]
    tpl_i = names.index("template") * 2 + 1
    tpl_root = etree.fromstring(bytes(arr[tpl_i].read_bytes()))
    top_name = next(c for c in tpl_root if isinstance(c.tag, str) and etree.QName(c).localname == "subform").get("name")

    if "datasets" in names:
        di = names.index("datasets") * 2 + 1
        root = etree.fromstring(bytes(arr[di].read_bytes()))
    else:
        # Aucun paquet de donnees (ex. IMM 5669) : on en cree un.
        root = etree.fromstring(('<xfa:datasets xmlns:xfa="%s"><xfa:data/></xfa:datasets>' % XFA_DATA_NS).encode())
        new_stream = pikepdf.Stream(pdf, b"")
        pos = tpl_i + 1
        arr = arr[:pos] + [pikepdf.String("datasets"), new_stream] + arr[pos:]
        pdf.Root.AcroForm.XFA = pikepdf.Array(arr)
        arr = list(pdf.Root.AcroForm.XFA)
        di = pos + 1

    data_el = [c for c in root.iter() if isinstance(c.tag, str) and etree.QName(c).localname == "data"][0]
    data_root = next((c for c in data_el if isinstance(c.tag, str)), None)
    if data_root is None:
        # Paquet de donnees vide (ex. IMM 0008) : on cree la racine du formulaire.
        data_root = etree.SubElement(data_el, top_name)
    lov_root = next((c for c in root if isinstance(c.tag, str) and etree.QName(c).localname == "LOVFile"), None)
    tfields = _template_fields(tpl_root)

    def node(path):
        cur = data_root  # la racine est deja le premier segment du chemin
        for name in path.split("/")[1:]:
            nxt = None
            for c in cur:
                if isinstance(c.tag, str) and etree.QName(c).localname == name:
                    nxt = c; break
            if nxt is None:
                nxt = etree.SubElement(cur, name)  # cree la structure manquante
            cur = nxt
        return cur

    remplis = []
    def put(path, val):
        if val is None or str(val).strip() == "": return
        val = _lov_code(tfields.get(path), str(val).strip(), lov_root)
        n = node(path)
        n.text = str(val); remplis.append(path.split("/")[-1])

    for key, path in cfg["map"].items():
        if key == "_dob":
            dob = (dossier.get("date_naissance") or "").split("-")
            if len(dob) == 3:
                for p, v in zip(path, dob): put(p, v)
            continue
        put(path, dossier.get(key))

    for key, paths in EXTRA.get(form_key, {}).items():
        for path in (paths if isinstance(paths, list) else [paths]):
            put(path, dossier.get(key))

    def _split_ym(v):
        v = (str(v) if v is not None else "").strip()
        if not v:
            return ("", "")
        parts = re.split(r"[-/]", v)
        if len(parts) >= 2:
            return (parts[0].strip(), parts[1].strip().zfill(2))
        return (v, "")

    # Historique scolaire et professionnel (1 etude + jusqu'a 3 emplois).
    hist = HISTORIQUE.get(form_key)
    if hist:
        def _fill_entry(src, mp):
            dy, dm = _split_ym(src.get("du"))
            ay, am = _split_ym(src.get("au"))
            derived = {"du_year": dy, "du_month": dm, "au_year": ay, "au_month": am}
            for sk, path in mp.items():
                put(path, derived[sk] if sk in derived else src.get(sk))

        etudes = dossier.get("etudes") or []
        if etudes and hist.get("education"):
            _fill_entry(etudes[0], hist["education"])
        emplois = dossier.get("emplois") or []
        emp_maps = hist.get("employment") or []
        for i, emp in enumerate(emplois[:len(emp_maps)]):
            _fill_entry(emp, emp_maps[i])

    # IMM 5669 : tableaux Etudes, Antecedents personnels et Adresses (AAAA-MM).
    if form_key == "IMM 5669":
        def ym(v):
            y, m = _split_ym(v)
            return (y + "-" + m) if (y and m) else y
        def lieu(e):
            return ", ".join(x for x in (e.get("ville"), e.get("pays")) if x)
        for i, e in enumerate((dossier.get("etudes") or [])[:5], 1):
            b = "IMM_5669/page2/educationTable/Row%d/" % i
            put(b + "fromDate", ym(e.get("du"))); put(b + "toDate", ym(e.get("au")))
            put(b + "Cell3", e.get("ecole")); put(b + "Cell4", lieu(e)); put(b + "Cell6", e.get("domaine"))
        for i, e in enumerate((dossier.get("emplois") or [])[:5], 1):
            b = "IMM_5669/page2/personalHistoryTable/Row%d/" % i
            put(b + "fromDate", ym(e.get("du"))); put(b + "toDate", ym(e.get("au")))
            put(b + "Cell3", e.get("poste")); put(b + "Cell4", lieu(e)); put(b + "Cell6", e.get("employeur"))
        b = "IMM_5669/page3/addressTable/Row1/"
        put(b + "Cell3", dossier.get("adresse_rue")); put(b + "Cell4", dossier.get("adresse_ville"))
        put(b + "Cell5", dossier.get("adresse_province")); put(b + "Cell6", dossier.get("adresse_code_postal"))
        put(b + "Cell7", dossier.get("adresse_pays") or dossier.get("pays_residence"))

    arr[di].write(etree.tostring(root, encoding="UTF-8"))
    buf = io.BytesIO(); pdf.save(buf)
    return buf.getvalue(), remplis, cfg["filename"]
