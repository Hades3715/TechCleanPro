"""
disco.py
Análisis completo de una unidad (1.8.0): qué carpetas y qué archivos se
llevan el espacio, con el árbol entero para ir entrando carpeta a carpeta.

Recorre con os.scandir en varios hilos. En Windows, scandir ya trae el
tamaño de cada archivo en el mismo listado de la carpeta (sin abrirlo), y
mientras espera al disco suelta el GIL, así que 8 hilos leen a la vez.
Medido en un C: de 300 GB y 713.000 archivos: 14 s. Con un hilo eran
50 s en caliente y hasta 400 s en frío; el analizador de antes (dos
niveles de profundidad) tardaba menos pero se dejaba casi todo sin contar.

Lo que NO se hizo: leer la MFT directamente, como WizTree. Necesita
administrador y un lector a mano de las estructuras de NTFS que en el
equipo de desarrollo no se pudo comprobar contra un disco real; con 14 s
no compensaba el riesgo de enseñar tamaños mal leídos.

Solo lee. No abre ningún archivo (así no despierta los de OneDrive que
están solo en la nube) y nunca borra nada: eso va por optimizer.
"""

import heapq
import os
import queue
import stat
import threading
import time

HILOS = 8
CUANTOS_GRANDES = 50

_REPARSE = 0x400
# Archivos y carpetas que están en la nube (OneDrive, Dropbox...): no ocupan
# disco, y LISTAR una carpeta así la bajaría de internet.
# RECALL_ON_DATA_ACCESS, RECALL_ON_OPEN, OFFLINE.
_EN_LA_NUBE = 0x00400000 | 0x00040000 | 0x1000

# Por tipo de archivo, para el reparto del espacio. La clave de idiomas de
# cada uno es "disco_tipo_<tipo>".
TIPOS = ("videos", "juegos", "programas", "comprimidos", "imagenes", "musica", "documentos", "registros",
         "otros")
_POR_EXTENSION = {
    "videos": "mp4 mkv avi mov wmv flv webm m4v mpg mpeg ts m2ts vob 3gp",
    # Los paquetes de datos de los motores de juego más comunes.
    "juegos": "pak vpk ucas utoc bsa ba2 forge bundle assets resource ress cpk rpf big wem bnk bank pck bik "
              "xnb sii scs wad gcf ff bsp unity3d",
    "programas": "exe dll sys msi msp msix appx cab mui ocx drv efi nls pdb lib a jar",
    "comprimidos": "zip rar 7z tar gz tgz bz2 xz zst iso img vhd vhdx vmdk vdi qcow2 wim esd",
    "imagenes": "jpg jpeg png gif bmp webp heic heif tif tiff raw cr2 cr3 nef arw dng psd svg ico",
    "musica": "mp3 wav flac aac ogg m4a wma opus aiff mid",
    "documentos": "pdf doc docx xls xlsx ppt pptx txt odt ods odp rtf csv epub md one pst ost",
    # Registros de programas y volcados de memoria tras un fallo. En el equipo
    # de desarrollo, los registros de un antivirus ocupaban 14,6 GB.
    "registros": "etl log dmp mdmp hdmp evtx blf",
}
_EXTENSIONES = {"." + ext: tipo for tipo, lista in _POR_EXTENSION.items() for ext in lista.split()}


def tipo_de(nombre):
    """El tipo de un archivo por su extensión ("otros" si no se conoce)."""
    punto = nombre.rfind(".")
    return _EXTENSIONES.get(nombre[punto:].lower(), "otros") if punto > 0 else "otros"


def es_de_la_nube(etiqueta):
    """IO_REPARSE_TAG_CLOUD y sus variantes (0x9000?01A): las carpetas que
    sincronizan OneDrive o Dropbox. Son puntos de análisis como las uniones,
    pero lo que tienen dentro SÍ es de esa carpeta."""
    return etiqueta & 0xFFFF0FFF == 0x9000001A


def se_entra(atributos, etiqueta):
    """¿Se recorre esta subcarpeta? No en uniones ni enlaces (lo de dentro
    es de otro sitio: contarlo sería contarlo dos veces, o en bucle) ni en
    las que solo están en la nube."""
    if atributos & _EN_LA_NUBE:
        return False
    return not atributos & _REPARSE or es_de_la_nube(etiqueta)


class Arbol:
    """El resultado. Solo guarda las CARPETAS (700.000 nombres de archivo
    serían ~100 MB): de cada una, lo que suman los archivos que tiene
    justo dentro. Además, los archivos más grandes de toda la unidad y lo
    que ocupa cada tipo.

    Las carpetas son índices: 0 es la raíz, y una subcarpeta siempre tiene
    un índice mayor que el de su madre (se da de alta al leer la madre).
    Por eso _sumar() es una sola pasada del final al principio."""

    def __init__(self, raiz):
        self.raiz = raiz
        self.nombres = [raiz]
        self.padres = [-1]
        self.propio = [0]       # bytes de los archivos que tiene justo dentro
        self.archivos = [0]     # cuántos archivos tiene justo dentro
        self.hijas = [[]]
        self.total = []         # bytes con todo lo de dentro (al terminar)
        self.archivos_total = []
        self.grandes = []       # [(bytes, ruta)], de mayor a menor
        self.tipos = dict.fromkeys(TIPOS, 0)
        self.n_archivos = 0
        self.sin_permiso = 0    # carpetas que no se pudieron leer
        self.segundos = 0.0
        self.cancelado = False

    def _nueva(self, nombre, padre):
        self.nombres.append(nombre)
        self.padres.append(padre)
        self.propio.append(0)
        self.archivos.append(0)
        self.hijas.append([])
        indice = len(self.nombres) - 1
        self.hijas[padre].append(indice)
        return indice

    def _sumar(self):
        total = list(self.propio)
        archivos = list(self.archivos)
        padres = self.padres
        for i in range(len(total) - 1, 0, -1):
            total[padres[i]] += total[i]
            archivos[padres[i]] += archivos[i]
        self.total = total
        self.archivos_total = archivos

    @property
    def bytes(self):
        return self.total[0] if self.total else 0

    def ruta(self, i):
        partes = []
        while i > 0:
            partes.append(self.nombres[i])
            i = self.padres[i]
        return os.path.join(self.raiz, *reversed(partes))

    def camino(self, i):
        """Los índices desde la raíz hasta i (para las migas de pan)."""
        lista = []
        while i >= 0:
            lista.append(i)
            i = self.padres[i]
        return lista[::-1]

    def hijas_de(self, i):
        """Las subcarpetas de i, de la que más ocupa a la que menos."""
        return sorted(self.hijas[i], key=self.total.__getitem__, reverse=True)

    def quitar_archivo(self, ruta, tam):
        """Descuenta un archivo que se acaba de mandar a la papelera, para
        no tener que volver a recorrer la unidad entera."""
        self.grandes = [g for g in self.grandes if g[1] != ruta]
        i = self.buscar(os.path.dirname(ruta))
        if i is None or not self.total:
            return
        self.propio[i] -= tam
        self.archivos[i] -= 1
        for j in self.camino(i):
            self.total[j] -= tam
            self.archivos_total[j] -= 1
        self.tipos[tipo_de(os.path.basename(ruta))] -= tam
        self.n_archivos -= 1

    def buscar(self, ruta):
        """El índice de una carpeta por su ruta (None si no se recorrió)."""
        relativa = os.path.relpath(os.path.normpath(ruta), os.path.normpath(self.raiz))
        i = 0
        if relativa == ".":
            return i
        for parte in relativa.split(os.sep):
            parte = parte.lower()
            i = next((h for h in self.hijas[i] if self.nombres[h].lower() == parte), None)
            if i is None:
                return None
        return i


def analizar(raiz, progreso=None, cancelar=None, hilos=HILOS):
    """Recorre `raiz` entera y devuelve un Arbol. Llamar desde un hilo
    aparte (tarda segundos).

    progreso(archivos, bytes): unas 4 veces por segundo, desde el hilo que
    llamó a analizar (no desde los que recorren).
    cancelar: un threading.Event. Si se pone, los hilos dejan de leer y se
    devuelve lo que se llevaba, con .cancelado = True."""
    arbol = Arbol(raiz)
    cola = queue.SimpleQueue()
    candado = threading.Lock()
    pendientes = [1]
    listo = threading.Event()
    cuentas = [[0, 0, 0] for _ in range(hilos)]    # archivos, bytes, carpetas sin permiso
    grandes = [[] for _ in range(hilos)]
    tipos = [dict.fromkeys(TIPOS, 0) for _ in range(hilos)]
    cola.put((raiz, 0))

    def leer(ruta, cuenta, monton, por_tipo):
        propio = archivos = 0
        subcarpetas = []
        try:
            with os.scandir(ruta) as it:
                for e in it:
                    try:
                        st = e.stat(follow_symlinks=False)
                    except OSError:
                        continue
                    atributos = st.st_file_attributes
                    if stat.S_ISDIR(st.st_mode):
                        if se_entra(atributos, st.st_reparse_tag):
                            subcarpetas.append((e.name, e.path))
                    elif not atributos & _EN_LA_NUBE:
                        tam = st.st_size
                        propio += tam
                        archivos += 1
                        por_tipo[tipo_de(e.name)] += tam
                        if len(monton) < CUANTOS_GRANDES:
                            heapq.heappush(monton, (tam, e.path))
                        elif tam > monton[0][0]:
                            heapq.heapreplace(monton, (tam, e.path))
        except OSError:
            cuenta[2] += 1
        cuenta[0] += archivos
        cuenta[1] += propio
        return propio, archivos, subcarpetas

    def trabajar(n):
        cuenta, monton, por_tipo = cuentas[n], grandes[n], tipos[n]
        while not listo.is_set():
            try:
                ruta, indice = cola.get(timeout=0.05)
            except queue.Empty:
                continue
            propio = archivos = 0
            subcarpetas = []
            if not (cancelar and cancelar.is_set()):
                try:
                    propio, archivos, subcarpetas = leer(ruta, cuenta, monton, por_tipo)
                except Exception:
                    # Lo que sea: esta carpeta se queda sin contar, pero la
                    # cuenta de pendientes tiene que bajar igual, o el
                    # análisis no terminaría nunca.
                    pass
            nuevas = []
            with candado:
                arbol.propio[indice] = propio
                arbol.archivos[indice] = archivos
                for nombre, ruta_hija in subcarpetas:
                    nuevas.append((ruta_hija, arbol._nueva(nombre, indice)))
                pendientes[0] += len(nuevas) - 1
                fin = pendientes[0] == 0
            for x in nuevas:
                cola.put(x)
            if fin:
                listo.set()

    inicio = time.perf_counter()
    trabajadores = [threading.Thread(target=trabajar, args=(n,), daemon=True) for n in range(hilos)]
    for h in trabajadores:
        h.start()
    while not listo.wait(0.25):
        if progreso:
            try:
                progreso(sum(c[0] for c in cuentas), sum(c[1] for c in cuentas))
            except Exception:
                pass
    for h in trabajadores:
        h.join()

    arbol.n_archivos = sum(c[0] for c in cuentas)
    arbol.sin_permiso = sum(c[2] for c in cuentas)
    arbol.grandes = heapq.nlargest(CUANTOS_GRANDES, (x for m in grandes for x in m))
    for por_tipo in tipos:
        for tipo, cuanto in por_tipo.items():
            arbol.tipos[tipo] += cuanto
    arbol.cancelado = bool(cancelar and cancelar.is_set())
    arbol._sumar()
    arbol.segundos = time.perf_counter() - inicio
    return arbol
