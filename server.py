import os, json, base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import fill_core as core

class H(BaseHTTPRequestHandler):
    def _s(self, code, obj):
        b = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code); self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        self._s(200, {"ok": True, "service": "IRCC XFA pre-fill", "formulaires": list(core.FORMS.keys())})
    def do_POST(self):
        try:
            tok = os.environ.get("FILL_TOKEN")
            if tok and self.headers.get("X-Fill-Token") != tok:
                return self._s(401, {"ok": False, "error": "token invalide"})
            n = int(self.headers.get("Content-Length") or 0)
            data = json.loads(self.rfile.read(n) or b"{}")
            # Mode multi-formulaires : remplit toute la liste et renvoie un ZIP unique.
            forms = data.get("formulaires")
            if isinstance(forms, list) and forms:
                import io, zipfile
                dossier = data.get("dossier") or {}
                did = str(data.get("dossier_id") or "dossier")
                buf = io.BytesIO(); infos = []
                with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
                    for f in forms:
                        fk = core.resolve_form(f)
                        if not fk:
                            infos.append({"formulaire": f, "ok": False, "error": "non gere"}); continue
                        try:
                            pdf, remplis, fn = core.fill(fk, dossier)
                        except Exception as fe:
                            infos.append({"formulaire": fk, "ok": False, "error": str(fe)}); continue
                        z.writestr(fn, pdf)
                        infos.append({"formulaire": fk, "ok": True, "filename": fn, "champs_remplis": len(remplis)})
                if not any(i.get("ok") for i in infos):
                    return self._s(422, {"ok": False, "error": "aucun formulaire rempli", "formulaires": infos})
                return self._s(200, {"ok": True, "filename": "Dossier_%s.zip" % did,
                                     "formulaires": infos, "zip_base64": base64.b64encode(buf.getvalue()).decode()})
            fk = core.resolve_form(data.get("formulaire"))
            if not fk: return self._s(400, {"ok": False, "error": "formulaire non gere", "disponibles": list(core.FORMS.keys())})
            pdf, remplis, fn = core.fill(fk, data.get("dossier") or {})
            self._s(200, {"ok": True, "formulaire": fk, "filename": fn, "champs_remplis": remplis, "pdf_base64": base64.b64encode(pdf).decode()})
        except Exception as e:
            self._s(500, {"ok": False, "error": str(e)})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    print("Fill service on :%d" % port)
    ThreadingHTTPServer(("0.0.0.0", port), H).serve_forever()
