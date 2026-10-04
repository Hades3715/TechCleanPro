# -*- coding: utf-8 -*-
"""Paso 5 del CONTEXTO, extendido a todos los modulos que usan t().

Ademas de la paridad es/en, comprueba:
  - claves usadas en el codigo que no estan definidas
  - claves definidas que nadie usa
  - placeholders {..} que no coinciden entre los dos idiomas (reventaria
    con KeyError solo en una de las dos builds)

Una clave cuenta como usada tanto si aparece dentro de t("...") como si
aparece suelta entre comillas: hay tablas (los codigos de error de
dispositivo, por ejemplo) que guardan el NOMBRE de la clave y la resuelven
despues con t(tabla[codigo]).
"""
import os
import re, glob, sys
import _rutas
RAIZ = _rutas.RAIZ
_rutas.poner_en_ruta()
import idiomas

es = set(idiomas.TEXTOS["es"])
en = set(idiomas.TEXTOS["en"])

directas = set()
sueltas = set()
# Se recorren los .py de codigo/, no los de la carpeta actual: con el
# glob relativo, correr esto desde cualquier sitio que no fuera la raiz
# no encontraba NINGUN archivo — y entonces "claves definidas sin usar"
# habria salido con la lista entera y "sin definir" vacia, o sea un
# resultado que parece un desastre y en realidad es que no leyo nada.
for f in glob.glob(os.path.join(_rutas.CODIGO, "*.py")):
    if os.path.basename(f) == "idiomas.py":
        continue
    codigo = open(f, encoding="utf-8").read()
    # quitar comentarios de linea para no contar claves citadas en comentarios
    sin_comentarios = "\n".join(re.sub(r"#.*$", "", l) for l in codigo.split("\n"))
    # Comillas dobles y simples: dentro de un f-string las llamadas a t()
    # van con simples (t('inf_titulo')), y antes no se veían.
    directas |= set(re.findall(r"""(?<![a-zA-Z_.])t\(["']([a-z_0-9]+)["']""", sin_comentarios))
    sueltas |= {s for s in re.findall(r"""["']([a-z_0-9]+)["']""", sin_comentarios) if s in es}

usadas = directas | sueltas
print(f"claves: es={len(es)} en={len(en)} | desbalance: {es ^ en or 'ninguno'}")
print(f"usadas en codigo: {len(usadas)} (directas {len(directas)}, indirectas {len(sueltas - directas)})")
print(f"sin definir: {directas - es or 'ninguna'}")
print(f"definidas sin usar: {es - usadas or 'ninguna'}")

malos = []
for k in es & en:
    pe = set(re.findall(r"\{(\w+)\}", idiomas.TEXTOS["es"][k]))
    pn = set(re.findall(r"\{(\w+)\}", idiomas.TEXTOS["en"][k]))
    if pe != pn:
        malos.append((k, sorted(pe), sorted(pn)))
print(f"placeholders desalineados: {malos or 'ninguno'}")

# Textos escritos a mano en la interfaz, sin pasar por t(). En la build en
# ingles salen en espanol. Aparecio una y otra vez ("Confirmar", "Protegido",
# "Terminar", "Desinstalar"...) porque nada lo buscaba.
import ast
PERMITIDOS = {
    "Mbps", "TechClean", "⚙ TechClean", "🪿 HONK!", "¿?",
    # El dialogo de idioma del primer arranque es bilingue por necesidad:
    # todavia no se sabe que idioma habla quien abre la app.
    "Idioma / Language", "Español", "English",
    "Selecciona tu idioma\nSelect your language",
    "Se puede cambiar después en Ajustes.\nYou can change this later in Settings.",
}
escritos_a_mano = []
for f in glob.glob(os.path.join(_rutas.CODIGO, "*.py")):
    if os.path.basename(f) == "idiomas.py":
        continue
    arbol = ast.parse(open(f, encoding="utf-8").read())
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, ast.Call):
            continue
        valores = [kw.value for kw in nodo.keywords if kw.arg in ("text", "title", "message")]
        if getattr(nodo.func, "attr", "") == "title" and nodo.args:
            valores.append(nodo.args[0])
        for v in valores:
            if (isinstance(v, ast.Constant) and isinstance(v.value, str)
                    and sum(c.isalpha() for c in v.value) >= 4 and v.value not in PERMITIDOS):
                escritos_a_mano.append(f"{os.path.basename(f)}:{nodo.lineno} {v.value!r}")
print(f"textos de interfaz sin traducir: {escritos_a_mano or 'ninguno'}")

# El codigo de salida es lo que mira Verificar_Todo.bat. Sin esto, este
# script imprimia los problemas y el banco lo daba por bueno igual.
problemas = (es ^ en) or (directas - es) or (es - usadas) or malos or escritos_a_mano
sys.exit(1 if problemas else 0)
