# -*- coding: utf-8 -*-
"""Rutina de auditoria del CONTEXTO_PROYECTO.md, pasos 2-4."""
import ast, collections
import _rutas

# Los .py de la app viven en codigo/. Se leen por _rutas.fuente() y no por
# nombre suelto: leerlos por nombre suelto dependia de que el .bat hubiera
# hecho cd a la raiz antes, asi que correr la auditoria a mano desde otra
# carpeta fallaba con "no such file".
#
# Las CLAVES del diccionario siguen siendo el nombre corto, porque son lo
# que se imprime en los mensajes y "main.py:DevConsole" se lee mejor que la
# ruta absoluta entera.
ARCH = ["main.py","optimizer.py","system_monitor.py","idiomas.py","widget.py",
        "tray.py","autopilot.py","privacy.py","report.py","preferences.py",
        "rutas.py","main_admin.py"]
arb = {f: ast.parse(_rutas.leer(f), f) for f in ARCH}

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
      "create_rectangle","delete","state","after_cancel","winfo_exists",
      "winfo_reqwidth","winfo_reqheight","winfo_children","pack","grid","bind","cget",
      # Falta ninguna de estas es un falso positivo: las hereda Tk, no las
      # define la clase. Se listan a mano porque el analisis es estatico y
      # no sabe de que hereda cada clase.
      "winfo_width","winfo_height","winfo_rootx","winfo_rooty","winfo_viewable",
      "winfo_toplevel","update","grab_set","grab_release","transient","resizable",
      "bind_all","unbind","event_generate","pack_forget","grid_forget","place",
      "wm_geometry","wm_attributes","iconify","focus_set","tkraise",
      "after_idle","create_line","create_polygon","create_oval","create_text",
      "create_window","coords","find_all","itemconfig","tag_lower","tag_raise",
      "icursor","insert","see","index","tag_config","tag_add","tag_remove",
      "yview","xview","selection_range","bindtags","lower","clipboard_get"}
# Miembros de cada clase, por archivo, para poder mirar los de la clase PADRE.
#
# Falso positivo que corregia esto: DevConsole y ComandoConsole llaman a
# self.imprimir(), que no definen ellas — la hereda _ConsolaBase, en el mismo
# archivo. Sin seguir la herencia, la auditoria marcaba las dos como si
# llamaran a un metodo inexistente, y ese ruido es peor que no comprobarlo:
# con tres o cuatro falsos positivos fijos, uno deja de leer la seccion.
def _miembros(nodo):
    m = {s.name for s in ast.walk(nodo) if isinstance(s,(ast.FunctionDef,ast.AsyncFunctionDef))}
    m |= {s.attr for s in ast.walk(nodo) if isinstance(s,ast.Attribute)
          and isinstance(s.value,ast.Name) and s.value.id=="self" and isinstance(s.ctx,ast.Store)}
    return m


clases = {}
for f, a in arb.items():
    for n in ast.walk(a):
        if isinstance(n, ast.ClassDef):
            clases[(f, n.name)] = n


def _heredados(f, nombre, vistos=None):
    """Todo lo que una clase recibe de sus padres, subiendo la cadena.

    `vistos` corta los ciclos: una jerarquia mal escrita con A(B) y B(A) no
    deberia colgar la auditoria."""
    vistos = vistos or set()
    nodo = clases.get((f, nombre))
    if nodo is None or (f, nombre) in vistos:
        return set()
    vistos.add((f, nombre))
    recogido = set()
    for base in nodo.bases:
        base_nombre = base.id if isinstance(base, ast.Name) else None
        if base_nombre and (f, base_nombre) in clases:
            recogido |= _miembros(clases[(f, base_nombre)])
            recogido |= _heredados(f, base_nombre, vistos)
    return recogido


r = []
for f, a in arb.items():
    for n in ast.walk(a):
        if not isinstance(n, ast.ClassDef): continue
        dfn = _miembros(n) | _heredados(f, n.name)
        cal = {s.func.attr for s in ast.walk(n) if isinstance(s,ast.Call)
               and isinstance(s.func,ast.Attribute) and isinstance(s.func.value,ast.Name)
               and s.func.value.id=="self"}
        falta = cal - dfn - TK
        if falta: r.append(f"{f}:{n.name} -> {sorted(falta)}")
print(r or "ninguno")
hallazgos = list(r)

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
hallazgos += r

# ---------------------------------------------------------------------------
# 5. El propio verificador
#
# Esta seccion existe porque Verificar_Todo.bat estuvo roto y NADIE lo vio.
# Ocho de sus lineas se habian escrito como "herramientas" + barra invertida +
# "revisar_algo.py", y esa barra seguida de r acabo convertida en un retorno
# de carro de verdad dentro del archivo. cmd leia entonces "python
# herramientas" —que falla— y "evisar_algo.py" como si fuera otro comando. Y
# como un .bat sigue con la linea siguiente cuando una falla, las ocho
# comprobaciones se saltaban en silencio: el banco imprimia sus titulos, no
# imprimia ningun FALLO, y parecia estar pasando entero.
#
# Es el aviso del CONTEXTO llevado al banco de pruebas: una comprobacion que
# no da error no es una comprobacion que se este ejecutando.
# ---------------------------------------------------------------------------
import io
import os
import re
import sys

BARRA = chr(92)

print("5. El verificador se ejecuta entero:", end=" ")
problemas = []
RUTA_BAT = os.path.join("herramientas", "Verificar_Todo.bat")

if not os.path.exists(RUTA_BAT):
    problemas.append("no existe " + RUTA_BAT)
else:
    crudo = io.open(RUTA_BAT, "rb").read()

    # Un CR que no forma parte de un CRLF es exactamente el sintoma.
    sueltos = crudo.replace(b"\r\n", b"").count(b"\r")
    if sueltos:
        problemas.append(str(sueltos) + " retorno(s) de carro suelto(s) — hay lineas partidas")

    # Un .bat necesita CRLF: con saltos de linea de Unix, cmd se come lineas.
    if crudo.count(b"\r\n") == 0 and crudo.count(b"\n") > 0:
        problemas.append("el archivo no tiene finales de linea de Windows (CRLF)")

    texto = crudo.decode("utf-8", errors="replace")

    # Se buscan los .py en cualquier posicion de la linea, no solo detras de
    # "python": los scripts se pasan como argumento a la subrutina
    # :comprobar, asi que un patron anclado en "python" no veria ninguno y
    # esta comprobacion diria que estan TODOS sin invocar. Las lineas REM se
    # saltan porque el comentario de arriba menciona una ruta a proposito.
    PATRON = re.compile("[" + BARRA + "w./" + BARRA + BARRA + "-]+" + BARRA + ".py")
    invocados = set()
    for linea in texto.splitlines():
        bajada = linea.strip().lower()
        # Las lineas REM llevan una ruta de ejemplo a proposito, y la del
        # mensaje de "instala Python" lleva una URL: sin saltarla, el
        # "www.python.org" de dentro se lee como un script llamado www.py.
        if bajada.startswith("rem") or "http" in bajada:
            continue
        for ruta in PATRON.findall(linea):
            invocados.add(os.path.basename(ruta.replace(BARRA, "/")))
            local = ruta.replace(BARRA, os.sep).replace("/", os.sep)
            if not os.path.exists(local):
                problemas.append("invoca un script que no existe: " + ruta)

    # Y al contrario: un banco de pruebas escrito y nunca llamado no protege
    # de nada. prueba_build y prueba_frozen se dejan fuera a proposito: las
    # dos compilan la app y tardan minutos, se corren aparte antes de
    # publicar. auditoria.py es este mismo archivo.
    APARTE = {"prueba_build.py", "prueba_frozen.py", "auditoria.py"}
    en_disco = {f for f in os.listdir("herramientas")
                if f.endswith(".py") and (f.startswith("prueba_")
                                          or f.startswith("revisar_")
                                          or f.startswith("verificar_"))}
    olvidados = sorted(en_disco - invocados - APARTE)
    if olvidados:
        problemas.append("escritos pero nunca invocados: " + ", ".join(olvidados))

print(problemas or "ninguno")
hallazgos += problemas

# El codigo de salida es lo que Verificar_Todo.bat mira para contar fallos.
# Sin esto, la auditoria podia encontrar cosas y el banco la daba por buena.
sys.exit(1 if hallazgos else 0)
