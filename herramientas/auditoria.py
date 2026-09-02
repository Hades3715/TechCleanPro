# -*- coding: utf-8 -*-
"""Rutina de auditoria del CONTEXTO_PROYECTO.md, pasos 2-4."""
import ast, collections
ARCH = ["main.py","optimizer.py","system_monitor.py","idiomas.py","widget.py",
        "tray.py","autopilot.py","privacy.py","report.py","preferences.py","main_admin.py"]
arb = {f: ast.parse(open(f, encoding="utf-8").read(), f) for f in ARCH}

print("2. Duplicados de clase/modulo:", end=" ")
d = []
for f, a in arb.items():
    c = collections.Counter(n.name for n in a.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)))
    d += [f"{f}:{k}" for k,v in c.items() if v>1]
    for n in a.body:
        if isinstance(n, ast.ClassDef):
            c = collections.Counter(m.name for m in n.body if isinstance(m,(ast.FunctionDef,ast.AsyncFunctionDef)))
            d += [f"{f}:{n.name}.{k}" for k,v in c.items() if v>1]
print(d or "ninguno")

print("3. self.X() sin definir:", end=" ")
TK = {"after","destroy","geometry","title","protocol","withdraw","deiconify","lift","iconbitmap",
      "minsize","focus_force","wait_window","grid_columnconfigure","grid_rowconfigure","attributes",
      "configure","overrideredirect","update_idletasks","clipboard_append","clipboard_clear",
      "winfo_pointerx","winfo_pointery","winfo_screenwidth","winfo_screenheight","winfo_x","winfo_y",
      "create_rectangle","delete","state"}
r = []
for f, a in arb.items():
    for n in ast.walk(a):
        if not isinstance(n, ast.ClassDef): continue
        dfn = {s.name for s in ast.walk(n) if isinstance(s,(ast.FunctionDef,ast.AsyncFunctionDef))}
        dfn |= {s.attr for s in ast.walk(n) if isinstance(s,ast.Attribute)
                and isinstance(s.value,ast.Name) and s.value.id=="self" and isinstance(s.ctx,ast.Store)}
        cal = {s.func.attr for s in ast.walk(n) if isinstance(s,ast.Call)
               and isinstance(s.func,ast.Attribute) and isinstance(s.func.value,ast.Name)
               and s.func.value.id=="self"}
        falta = cal - dfn - TK
        if falta: r.append(f"{f}:{n.name} -> {sorted(falta)}")
print(r or "ninguno")

print("4. opt.X / sysmon.X inexistentes:", end=" ")
pub = {}
for mod, arch in [("optimizer","optimizer.py"),("system_monitor","system_monitor.py"),
                  ("idiomas","idiomas.py"),("privacy","privacy.py"),
                  ("preferences","preferences.py"),("report","report.py")]:
    ns=set()
    for n in arb[arch].body:
        if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)): ns.add(n.name)
        elif isinstance(n,ast.Assign):
            ns |= {t.id for t in n.targets if isinstance(t,ast.Name)}
        elif isinstance(n,(ast.Import,ast.ImportFrom)):
            ns |= {al.asname or al.name.split(".")[0] for al in n.names}
    pub[mod]=ns
r=[]
for f in ARCH:
    for n in ast.walk(arb[f]):
        if isinstance(n,ast.Import):
            for al in n.names:
                if al.name in pub:
                    a2 = al.asname or al.name
                    used = {s.attr for s in ast.walk(arb[f]) if isinstance(s,ast.Attribute)
                            and isinstance(s.value,ast.Name) and s.value.id==a2}
                    falta = used - pub[al.name]
                    if falta: r.append(f"{f}: {a2}.{sorted(falta)}")
print(r or "ninguno")
