#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
07_honeycomb_tabs_drawer_fix.py - Launcher2: linha das abas do Honeycomb, gaveta translucida e crash ao arrastar widget

Rode na RAIZ do repositorio (depois do 05 e do 06):
    python3 07_honeycomb_tabs_drawer_fix.py [--dry-run]

1) CRASH AO SEGURAR/ARRASTAR UM WIDGET
   Workspace.drawDragView usava `clipRect(rect, Op.REPLACE)` (Region.Op.REPLACE foi removido no
   Android 9+). O script 06 so tratava BubbleTextView e CellLayout; este varre TODOS os .java:
   qualquer `clipRect/clipPath(..., [Region.]Op.REPLACE)` vira a versao de 1 argumento (o canvas
   desses bitmaps e' novo, entao INTERSECT == REPLACE).

2) LINHA FINA DAS ABAS (entre "Apps" e "Widgets") NO TOM DO HONEYCOMB
   Comparei o res/ do APK do Launcher2 do Honeycomb com o do ICS. Dos drawables que existem nos
   dois, 40 sao identicos; os unicos que mudam de aparencia sao a familia tab_unselected_*:
       ICS       -> linha fina #33b5e5 (azul claro do Holo)
       Honeycomb -> linha fina #6595f9 (o MESMO tom da barra grossa da aba selecionada)
   Este script instala a versao do Honeycomb (hdpi + mdpi) de:
       tab_unselected_holo / tab_unselected_focused_holo
       tab_unselected_pressed_holo / tab_unselected_pressed_focused_holo
   e REMOVE as versoes xhdpi do ICS. Isso e' necessario: no A35 (densidade 450) o Android usa a
   pasta xhdpi, entao a linha clara do ICS continuaria aparecendo e a barra grossa (que so existe
   em hdpi/mdpi) vinha do Honeycomb: tons diferentes. Sem xhdpi, as duas vem do mesmo lugar.
   (Os PNGs do APK vem "compilados"; aqui estao embutidos ja reconstruidos como 9-patch fonte.)
   Nao troquei os demais drawables: gardening_crosshairs, homescreen_small_blue* e
   ic_home_all_apps_holo_dark sao os ICS de proposito (grade/botao de apps mais nitidos).

3) GAVETA DE APPS TRANSLUCIDA COM O WALLPAPER ESCURECIDO (como no Honeycomb)
   * res/drawable-nodpi/all_apps_bg_gradient.9.png = gradiente preto do Honeycomb
     (alpha 85% no topo -> 50% embaixo), usado como fundo da gaveta.
   * Launcher.updateWallpaperVisibility: o ICS DESLIGAVA o wallpaper (FLAG_SHOW_WALLPAPER) quando
     a gaveta abria, porque la o fundo era opaco; sem isso o fundo translucido mostrava preto.
     Agora o wallpaper fica sempre ligado.

Idempotente. Pontos nao encontrados sao listados no final como AVISO.
"""
import base64
import re
import sys
from pathlib import Path

DRY = "--dry-run" in sys.argv
SRC = Path("src/com/android/launcher2")
RES = Path("res")
CHANGED, WARN = [], []

DRAWABLES = {
    'drawable-hdpi/tab_unselected_focused_holo.9.png': (
        'iVBORw0KGgoAAAANSUhEUgAAAAoAAABKCAYAAACCasXRAAAAg0lEQVR4XmNgwAT/GRjAGAWwgHgz'
        'zyBJ/GdoBKtgRIilmzAwMGExESsgWiHI6v9w6xgYGNJNGRrAzjmNYnA90SaCFDIS406STCQKjJqI'
        'F4wGz2jwYIDRRDGaKEYTBRiMZoXRrDCaFQY6K4DbjqlTf2K0kpHB7Gx2GmRXWLMVr9Wg5i0ArxwS'
        'kBXwjfQAAAAASUVORK5CYII='
    ),
    'drawable-hdpi/tab_unselected_holo.9.png': (
        'iVBORw0KGgoAAAANSUhEUgAAAAQAAAAHCAYAAAAvZezQAAAALElEQVR4XmNggID/UAznwMB/JjgT'
        'ChhBdOrUnyAtDLOz2RkwVGAIwA2D2QIAjekKAfs9MeEAAAAASUVORK5CYII='
    ),
    'drawable-hdpi/tab_unselected_pressed_focused_holo.9.png': (
        'iVBORw0KGgoAAAANSUhEUgAAAAoAAABKCAYAAACCasXRAAACFUlEQVR4XrVWO07EQAy1J0hUcBEo'
        'KaHiDtwAUXAeCsQJ4A5UUFLCRRYJCZaMkX8zzkeQiVhLkTJZx89+fnYWYGoEINfA9vh0+1J/eN+c'
        '3fOzg8On4nx1AuoYjYBwBgXS3MM544i02Zw++I+vb49yf3x0HvyfLxZHZEfJCSkhXx4m3rM1RVxk'
        'Qk+EIdJUxs8nPKZcHaO150iAyJdHifdsAj1wwAodn7dD/2X/H7HwSKQVO+F8RqQi3h1BO6xARx4t'
        'nUK4OliO1mtLsT1HbaFFi1WPn5eqOZ9BriG/plGYCBdD1dE0R4bxzrjCOZXguaPOOKypvaKEyhdD'
        'V5lBp6vFquYzQl/qseHqStXZ1wxXjV2pezH0YkfNUaozmfX+MjehMt4YkdeJcebF6HDViKXXrsnk'
        '9LDbamgGyTPQdaPbNsulcoAos7xmAVThOo9lhw9naEI4lk9KVf2a4QqEI4hklPBKuelxkI+0dezY'
        '1mvrs0bqy8wkojqxpnB20nw8RxEKUEFsg1bhJn3JqpYz1f1oay8lygZNSg+LBJO93PJhr8Ilq9Yi'
        'ynlctcww6QIgcsI76YIPQ1vVBusv+ZqZI5ypsAotRz7TaoVzMdkVnjUFPqfxl0v+Ehg9pdckfjJ3'
        'TYS30aNiUO2xtuK5GVrI7fB7mzFL4l2CD0k+fW0T5N4jSi8vbz4n/5Kj3V3vLy9mcdUuo1+hmYwf'
        'ZMrThIxZ7gUAAAAASUVORK5CYII='
    ),
    'drawable-hdpi/tab_unselected_pressed_holo.9.png': (
        'iVBORw0KGgoAAAANSUhEUgAAAAQAAABKCAYAAACco/ViAAAA0UlEQVR4XrVUSw4CMQilHRO37ryX'
        'R/ACnsBDeAGPaTKLAUNpS0f600SSJh2G9x5QWgAxigsOvLk+1gt7n7cj+RiRjR0OnSz2MgQofrBV'
        'ITsbRwgpiUJW8aiOWY5/J/ZDHlJcrxZT/qSKK6odqxhSgYDLP+oRRgWLQ5/MlDaNrKuUpCEx3zvK'
        'EGEg3zU5cLheLaLiYNmNZTnzjZ5u2lPDUYfApwqSyjYgRUSaoMFRpvurm6EKoZKOa2lMEIUnp/5c'
        'BNLFw2vX5PMJ702IUUmWH7Y3yBs120LMJh8AAAAASUVORK5CYII='
    ),
    'drawable-mdpi/tab_unselected_focused_holo.9.png': (
        'iVBORw0KGgoAAAANSUhEUgAAAAcAAAAyCAYAAACQ5cHNAAAAZUlEQVR4XmNgQAX/kbksIM7MM1DB'
        '/wyNDIwQdroJAwMTmk4UANL5H6wDpNqUoWHmabh8PUgnIy7deI0dlWQgEPCjITQaQhAwmhIGKBDA'
        'RVvq1J8oRSkIzM5mxx8rsEIRQyeowAQAQeURYXBQ8kcAAAAASUVORK5CYII='
    ),
    'drawable-mdpi/tab_unselected_holo.9.png': (
        'iVBORw0KGgoAAAANSUhEUgAAAAMAAAAFCAYAAACAcVaiAAAAHklEQVR4XmNggID/UBrOgAikTv0J'
        'YvxngkkjA7ASAA9zB/CZIYjTAAAAAElFTkSuQmCC'
    ),
    'drawable-mdpi/tab_unselected_pressed_focused_holo.9.png': (
        'iVBORw0KGgoAAAANSUhEUgAAAAcAAAAyCAYAAACQ5cHNAAABlklEQVR4XpVUPU6DMQy1HSQmuAiM'
        'jDBxB26AGDgPA+IE9A5MMDLCRYpUCUpj9PyTL+kHBSxVbmL7+fkl+YhG0365h8Xts2++Lc/uDw4f'
        '7f/VCZH0mUrK25W6XJ4usPny+rA4PjqP+NMFKi2bVQYPG2C3zYJZpTqiDJVSPZjWgkpsgfStZwuw'
        'V+b6d0I/2dRTmcEWfkboO7PKzG6EonqCZWatxPADbG6kQrkeCPUtZsJziJBmN8EIYBRoCx/RPygU'
        '1JXYk2ejUMEQDD+Ogg1lrrgZ1tMTdvY0tt6DWTdIBnMHjkqciMO6ri5hmxOSCQiBVl/JEL2rhDXY'
        'Gn1TIVtnz+zjp+IoE6EgwUbQdZ6zZSo922EUtJkFo4foxoSPhBBBoxdgjVDsd0ckQhYUE38ahUUq'
        'RFAq8FiP8ikLqbFFpQnYYFULRBD4hE3hjWUcBNhapQeNBH5U4BUYPWzFCNVe/iifvWRlsTmV5Z8v'
        'G+OpgbSPoxEq/LmuXGsRWol8rIXqBvsm0+XN+/Aphd1d7+++t3n1Z5VA/QJZPMAkeFpr/gAAAABJ'
        'RU5ErkJggg=='
    ),
    'drawable-mdpi/tab_unselected_pressed_holo.9.png': (
        'iVBORw0KGgoAAAANSUhEUgAAAAMAAAAyCAYAAACZDmG3AAAAmklEQVR4Xp1SwRHCMAyTUwbgx1ys'
        'wB4MwbLc8ajFxWmLxJEPfqQn27LkpMAIbl/w9nhde6IBiAxEr3QAKtijKgZI4bQU4G1/TJsPoOqY'
        'A+OE7TP3hqi96jBObskfa68jWYe1NRW1ytx1qE4GlmP0LjGeZBWj3qacpA5QQIprAKePjrWlLvdl'
        'p2JcFcePVGBpeB7gcs67rmBRnDfI3zFOoZle4QAAAABJRU5ErkJggg=='
    ),
    'drawable-nodpi/all_apps_bg_gradient.9.png': (
        'iVBORw0KGgoAAAANSUhEUgAAAAMAAAMiCAYAAACrMHmxAAABJUlEQVR4Xu1a0Q6DIAzU/f8X7mO2'
        'RdAIJpDm2lLIjgcT1F7b61FIdNvy+B6X1zl5HzeuSRqaSQWtRmsDOPopofcygvRgInZsOYhA69Ab'
        'EU5bb3sZDqQDdT4hADKn6jLWADKndbEQm2o5IwC0eewlwgYJ8CZcgMOEBKQAbSxaP8ZbKLI3ClMQ'
        'vjZq0TqG4wiNsOMYjiN0M9N8ej3PsB8ZIYgNxLUsHOg1BHqUTYQOHDtfB3oUo4ifyaqApBBiE+J0'
        'VLHUyakBkEzVTglg3SBtGXVEk0F3jgQVgAytY9NG+xs/ENcIb7SxVuKSjFJvc+uA9Zm7PmuuekZt'
        'rSquU2tGqVEyeg/Nh/glD2aMmvKn/AsK2AKUf9ywDbKpsqku1FTzz1XFSDd+IMJzvjf5DA0AAAAA'
        'SUVORK5CYII='
    ),
}

# xhdpi do ICS que escondem a versao do Honeycomb (a linha clara #33b5e5)
REMOVE = [
    "res/drawable-xhdpi/tab_unselected_holo.9.png",
    "res/drawable-xhdpi/tab_unselected_focused_holo.9.png",
    "res/drawable-xhdpi/tab_unselected_pressed_holo.9.png",
    "res/drawable-xhdpi/tab_unselected_pressed_focused_holo.9.png",
    "res/drawable-xxhdpi/tab_unselected_holo.9.png",
    "res/drawable-xxhdpi/tab_unselected_focused_holo.9.png",
    "res/drawable-xxhdpi/tab_unselected_pressed_holo.9.png",
    "res/drawable-xxhdpi/tab_unselected_pressed_focused_holo.9.png",
]


def rd(p):
    return Path(p).read_text(encoding="utf-8")


def wr(p, t):
    if not DRY:
        Path(p).write_text(t, encoding="utf-8")


def edit(path, old, new, marker=None, desc=None):
    p = Path(path)
    tag = f"{p.name}: {desc or old.strip()[:50]!r}"
    if not p.exists():
        WARN.append(tag + " (arquivo inexistente)")
        return
    t = rd(p)
    if marker is not None and marker in t:
        return
    if old not in t:
        if marker is None and new in t:
            return
        WARN.append(tag + " (trecho nao encontrado)")
        return
    wr(p, t.replace(old, new, 1))
    CHANGED.append(tag)


# ------------------------------------------------------------------ 1) Region.Op.REPLACE em todo o src
REPL = re.compile(r",\s*(?:android\.graphics\.)?(?:Region\.)?Op\.REPLACE\s*\)")
for p in sorted(SRC.glob("*.java")):
    t = rd(p)
    # Utilities.clipRectExpand usa REPLACE de proposito (protegido por SDK_INT < 28)
    if p.name == "Utilities.java":
        continue
    new, n = REPL.subn(")", t)
    if n:
        wr(p, new)
        CHANGED.append(f"{p.name}: {n}x clip(..., Op.REPLACE) -> clip(...)")

# ------------------------------------------------------------------ 2) drawables do Honeycomb
for rel, b64 in DRAWABLES.items():
    data = base64.b64decode("".join(b64))
    dst = RES / rel
    if dst.exists() and dst.read_bytes() == data:
        continue
    if not DRY:
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(data)
    CHANGED.append(f"res/{rel}: instalado (Honeycomb)")

for rel in REMOVE:
    p = Path(rel)
    if p.exists():
        if not DRY:
            p.unlink()
        CHANGED.append(f"{rel}: removido (ICS)")

# ------------------------------------------------------------------ 3) gaveta translucida
_pane = RES / "layout/apps_customize_pane.xml"
if _pane.exists():
    _t = rd(_pane)
    if "@drawable/all_apps_bg_gradient" not in _t:
        # fundo translucido do 05 (@color/apps_customize_bg_color) ou o preto opaco do ICS
        for _old in ('android:background="@color/apps_customize_bg_color">',
                     'android:background="#FF000000">'):
            if _old in _t:
                wr(_pane, _t.replace(_old, 'android:background="@drawable/all_apps_bg_gradient">', 1))
                CHANGED.append("apps_customize_pane.xml: fundo da gaveta = gradiente do Honeycomb")
                break
        else:
            WARN.append("apps_customize_pane.xml: fundo da gaveta nao encontrado")
else:
    WARN.append("res/layout/apps_customize_pane.xml inexistente")

edit(SRC / "Launcher.java",
     "        int wpflags = visible ? WindowManager.LayoutParams.FLAG_SHOW_WALLPAPER : 0;",
     "        // Gaveta translucida (Honeycomb): o wallpaper nunca pode ser desligado.\n"
     "        int wpflags = WindowManager.LayoutParams.FLAG_SHOW_WALLPAPER;",
     marker="Gaveta translucida (Honeycomb)", desc="wallpaper sempre visivel")

# ------------------------------------------------------------------ resumo
print("== 07: abas Honeycomb + gaveta translucida + clip do drag ==" + ("  (dry-run)" if DRY else ""))
for c in CHANGED:
    print("  ok  ", c)
if not CHANGED and not WARN:
    print("  nada a fazer (ja aplicado)")
if WARN:
    print("AVISOS:")
    for w in WARN:
        print("  !!  ", w)
