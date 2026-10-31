#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
09_honeycomb_colors.py - cores/outlines/bordas do Launcher2 ICS trocados pelos do Honeycomb

Rode na RAIZ do repo (depois do 08):  python3 09_honeycomb_colors.py [--dry-run]   (idempotente)

CORES (extraidas do APK do Honeycomb: res/values/colors.xml + uso no smali/Java)
  drag_outline_color                      #ff6595f9   contorno do item ao ARRASTAR / soltar
  workspace_item_pressed_outline_color    #ff6595f9   icone pressionado (brilho externo)
  workspace_item_pressed_glow_color       #ff0997ff   icone pressionado (linha brilhante)
  workspace_item_focused_*                idem (foco por teclado)
  O ICS usava android.R.color.holo_blue_light (#33b5e5) em tudo isso.

O QUE MUDA
  1. res/values/colors.xml: 5 cores do Honeycomb.
  2. BubbleTextView: pressed/focused com as cores do Honeycomb (mesma ordem glow/outline do HC).
  3. Workspace: 4 outlines de arrasto (createDragOutline etc.) -> drag_outline_color.
  4. HolographicViewHelper (estados pressed/focused de pastas/botoes) -> cor do Honeycomb.
  5. user_folder.xml: nome da pasta #33b5e5 -> #6595f9.
  6. Drawables do Honeycomb (hdpi+mdpi, 9-patch reais decodificados do APK):
       homescreen_small_blue, homescreen_small_blue_strong  (borda das paginas encolhidas)
       gardening_crosshairs, widget_resize_frame_holo, divider_launcher_holo
     e remove as versoes xhdpi do ICS (o A35, densidade 450, usa xhdpi: sem remover,
     a versao azul-ciano do ICS continuaria aparecendo).
  Os PNGs vao embutidos neste script; nao precisa do APK.
Pontos nao encontrados sao listados no final como AVISO (exit 1).
"""
import base64
import sys
from pathlib import Path

DRY = "--dry-run" in sys.argv
SRC = Path("src/com/android/launcher2")
RES = Path("res")
CHANGED, WARN = [], []

ASSETS = {
    "drawable-hdpi/homescreen_small_blue.9.png":
        "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"
        "QmCC"
    ,
    "drawable-mdpi/homescreen_small_blue.9.png":
        "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"
        "pfEB+J1aVdu/NOcYwVfINGAAAAAASUVORK5CYII="
    ,
    "drawable-hdpi/homescreen_small_blue_strong.9.png":
        "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"
        "TkSuQmCC"
    ,
    "drawable-mdpi/homescreen_small_blue_strong.9.png":
        "iVBORw0KGgoAAAANSUhEUgAAADwAAAA8CAYAAAA6/NlyAAAGhUlEQVR4Xu2aW2xUZRDHx3Z7oZUWvMRLjDGKqA+EB4wYDdHEJyX6"
        "oCGRBC9R0xoEAbXQ0oAUqFwEBETaKjSaSMID8Rrjk2JIjBFfTJDgLRoTpS1GW9pCC7QZ5zfnnM12LUJ3uwV79ksmp+e7zP//P998"
        "M6e7K3JhmqZ35Fu+5Vu+jVHTS8bOxrylgK/SgiE2RwtzZulYuX8IKSIDAgmp0iK7Frst1JKcW4QV4CaSD2L0hacIBQzwJTpBXtJy"
        "+7tClv1dKYs7J0lt1+ScGf7BAQ9c8OEBnyHCs25DdrU4BKqQJccvk+W9V8nSE9fKsr7rpbbvBqntv3GI1fTflLGl+8I/OOCBC77z"
        "MD7wGj3R5iASW6Vl/rRreq92AnWnbpUVp6dL/enb7TpT6s/cJXVn7k7aijOzMrZUP/h1/44z3XHBdx7GB16R6OwEh7tL2PAkcc4T"
        "ruufasAzjNg9snJgttkjZnOlYeAxsydk1cCTo2b4wy/+A5zZjgs+POADL/gFZzubXQ53N0gaFf5EA7EzDfh+eXlgnqweXCBrtVbW"
        "DjbIK4ON0qjr7bph1Czw1+j+wQEPXPDhAR94wQ+e2e2y73DCnx5nhjDiyQLWMPC0EVhesE63FKzX3YWbdK/Z+4Wb9cPEJv1otAx/"
        "7tf8gwMeuI4fiJ7hvOAXnOdE5oKjcCYrkij8zFo48YQRu0GbIJPYovuLt+nXxdv125Lteqjkdf0uadyP1NLW4xf/4IAHrouGB3zg"
        "BT94JsM6kxYUeWpshZ8VEgZnyMKKJw148Vb9yogdmbBDf5vQpEfLm7XdrCO09rIWt7ayZm1j/GzGuM9r8fVDfPgc8w8OeC6anSa8"
        "/UwbL/jBM6jVmQgOExYOqH+UBLIkicPOEuHFE4cERMvf0s6Jrdpj1uu2y63H+rvL39Tjdu06pwXzulnn6yNfre6nExzwwAXfzzR8"
        "4AU/eCYFjzisQ8EkAn+p8PNLsppLAuFMEWY8echUturJire13+yUX1u179JWPVG+W3vNzi2acebZfNaxPtUf/sEBD1zwPZHBB17w"
        "g2fwRpah4ChD+9uOFX/qISXCsqaHs50two0dgNSkd/R0pRl/T4SgCSiDZIv+Vdqsf5Y26TGzjpImbY+Me++3ceYxn3Wsd6HmD7+h"
        "zx7wwAXfszd84OUvJ8Yz80w9jGBeAqiLVirIniQUzhhhx06EYk+xQ0a8CyGJN/T3wu36a8E2/Vm26Y9mP8hr+n3SuLd+xpnHfNax"
        "3nc6xS844IELvpcs+MArZ4J5GbD6SMkgi5JYQsGEX7+LbdHO4p161EVuHjwkG/sOSuOJL6Wx54Cs6fpC1nbvTxr39DPOPJvPOtbj"
        "JxTtvkPBHeCC73UaPmMu2BIMZ44wZGcg67u37uRBWd35mdT/8bHU/LJPXvxpryw5skcWHd4jzx9+16/c088485jPOlvvos2fhzf+"
        "d42lYF7oecf9t+B2smqYoLoJR99ZSK849qmLmf/NLnnq8x3y+CdbZd4HW+TR915NGvf0M8485rPO1uMHf/jFv2d9QjpdMLz8H45c"
        "C7az5HWT0mPZlYTDGfQwZqcg/8yBnTJn70Z5YOcauW/9Srm3oV5m1S9PGvf0M8485rOO9eYHf2Ei6wUHPHCzEKzpHWE7b8FtUUkh"
        "y5J4/CwSnuwYIhB0x4KlMm3uC3LLw4vl5ocWyZQHgyv39DPOPOazjvXmB3/4jUqb1+ILKrjZXzq8jlJaPJxJQJxJwpSdQwzirrtz"
        "oVw57Tm5/DazqcGVe/oZZx7zWcd68+NhbX6jOg7eBRXsr5PhywPnzUsPWZew5Gyya+wgoiZPmS9l1zwrJVeYVVb7lXv6GWce81nH"
        "evyYPz/HIQZ4F5PgDq+rlBqyLwmJM0rYspOIKyqrlqLSKikoCq7c088485jPOtbjx/zh96IUzJuTlyPqKyWHLExiIlwJX3YUkYWF"
        "VSIF1X7lnn7Gmcd81rEeP+YPv6MteBjVWQqmzkaCSVCcWcKYnUWsSCCae/oZZ14kmPU5FDxMy1LwRb7Dw7SRC47dGY5Flo5dHY7f"
        "m9b/7136bO08BI/r/5Zi9//wfwke1594xOozrXH/qWXsPpeO1zcPErfvliSG3x4GYR2j74dTM3WMfgEQp9940MJdjseveGjhLkei"
        "x//vtGgposf/L/GihrMhuz2ef2uZ2iLnofhUg0CuLB0rlcfYt1TwXFu+5Vu+5Vu+5aTpCCyn7R/i+U7OZWQgWQAAAABJRU5ErkJg"
        "gg=="
    ,
    "drawable-hdpi/gardening_crosshairs.png":
        "iVBORw0KGgoAAAANSUhEUgAAABcAAAAXCAMAAADX9CSSAAAAeFBMVEX///8AABAAABAAAAgAAAAAAAgNMG4NMHghef8NMHgNLm4i"
        "dv8NLm4OL24jeP8OL24QMW4off8TNG4whf8TNG46kP8AAAoNMG4NL24TNG4XOWVHnP8WOGUQMW4AABBOn/9Hmf85jv8WOGUQMW4O"
        "L24QMW4OL24NLm4VoKiVAAAAKHRSTlMAAwQCAAFnaNdnaMpmbMxrcs530HbUBGhneHHWcXEC19bUcG9pcGpnnBcZJgAAAItJREFU"
        "KM+V0MsSgjAMBdAEMVYrfdggRXyAz///Q4WF00W66F2eyWSSC/APVghSVvUaSkJEom/UVvSd3oveGCu68070Q2DZ29TxCNTFxvX9"
        "aTgzX2zsfudeoaqBlDY+tMNtnII3Wi0+z1O08/x4Z348Iy2e7J+46B7nX5l/36J/Mv3k+sz1XxrE5MsvhtkHMCEcNZ0AAAAASUVO"
        "RK5CYII="
    ,
    "drawable-mdpi/gardening_crosshairs.png":
        "iVBORw0KGgoAAAANSUhEUgAAAA8AAAAPCAMAAAAMCGV4AAAAVFBMVEX///8AABAAABAAABAAABAAABAAABAcav8AABAAABAidf8A"
        "ABAAABAlev8AABAAABAvhP8AABAAABAAABBAlv8AABBOn/8/k/8AABAAABAAABAAABDTJYOsAAAAHHRSTlMAAgQKEAkWwhQhyR8p"
        "zSg00DIgP9UB19UPPiYDncnKUQAAAGRJREFUCNddjkkSgCAMBImoIDsBFfH//3TjYOhTuqaSDGMvMAD7w8eJ+Cwk8UVp4sY64j7E"
        "NgGf0fiUU3Qop5UNo1A25G0PVokCdy7R+bQfseon7/c/nK3Esfvf9+OF9oezXb4Ar8wD45Tpa5YAAAAASUVORK5CYII="
    ,
    "drawable-hdpi/widget_resize_frame_holo.9.png":
        "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"
    ,
    "drawable-mdpi/widget_resize_frame_holo.9.png":
        "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"
    ,
    "drawable-hdpi/divider_launcher_holo.9.png":
        "iVBORw0KGgoAAAANSUhEUgAAAAwAAAAwCAYAAAAlzZsxAAAAUklEQVR4XmNgwA3+QzH1AR8Ui0MxiI0XkKwBrPD///92IAxkGyPJ"
        "YfXTqAaGUQ2jGuCAoAZ0XdTXgA5GNTCMahjVAAdDTANWQHLFTj8A8iCGJwHf2z+DtT+7UgAAAABJRU5ErkJggg=="
    ,
    "drawable-mdpi/divider_launcher_holo.9.png":
        "iVBORw0KGgoAAAANSUhEUgAAAAgAAAAgCAYAAAAv8DnQAAAAPUlEQVR4XmNgwAT/0QVIAnxALA6lsQLx////2wFpYygfw7pRBRBA"
        "IwXIqrAqQAajCiBgSCggmPWIAijGAgAIHnjMTZ7HgAAAAABJRU5ErkJggg=="
    ,
}


def rd(p):
    return Path(p).read_text(encoding="utf-8")

def wr(p, t):
    if not DRY:
        Path(p).write_text(t, encoding="utf-8")

def edit(path, old, new, marker, desc, count=1):
    p = Path(path)
    tag = f"{p.name}: {desc}"
    if not p.exists():
        WARN.append(tag + " (arquivo inexistente)")
        return
    t = rd(p)
    if marker in t:
        return
    if old not in t:
        WARN.append(tag + " (trecho nao encontrado)")
        return
    wr(p, t.replace(old, new) if count == 0 else t.replace(old, new, count))
    CHANGED.append(tag)

# 1) colors.xml ---------------------------------------------------------------------------
edit(RES / "values/colors.xml",
     "</resources>",
     "    <!-- [09] cores do Launcher2 Honeycomb -->\n"
     '    <color name="drag_outline_color">#ff6595f9</color>\n'
     '    <color name="workspace_item_pressed_outline_color">#ff6595f9</color>\n'
     '    <color name="workspace_item_pressed_glow_color">#ff0997ff</color>\n'
     '    <color name="workspace_item_focused_outline_color">#ff6595f9</color>\n'
     '    <color name="workspace_item_focused_glow_color">#ff0997ff</color>\n'
     "</resources>",
     marker="name=\"drag_outline_color\"", desc="cores do Honeycomb")

# 2) BubbleTextView -----------------------------------------------------------------------
edit(SRC / "BubbleTextView.java",
     "        mFocusedOutlineColor = mFocusedGlowColor = mPressedOutlineColor = mPressedGlowColor =\n"
     "            res.getColor(android.R.color.holo_blue_light);\n",
     "        // [09] cores do Honeycomb (em vez de holo_blue_light)\n"
     "        mFocusedOutlineColor = res.getColor(R.color.workspace_item_focused_outline_color);\n"
     "        mFocusedGlowColor = res.getColor(R.color.workspace_item_focused_glow_color);\n"
     "        mPressedOutlineColor = res.getColor(R.color.workspace_item_pressed_outline_color);\n"
     "        mPressedGlowColor = res.getColor(R.color.workspace_item_pressed_glow_color);\n",
     marker="[09] cores do Honeycomb (em vez de", desc="pressed/focused")

# 3) Workspace ----------------------------------------------------------------------------
ws = SRC / "Workspace.java"
edit(ws, "getResources().getColor(android.R.color.holo_blue_light)",
     "getResources().getColor(R.color.drag_outline_color)",
     marker="getResources().getColor(R.color.drag_outline_color)",
     desc="outlines de arrasto (getResources)", count=0)
edit(ws, "r.getColor(android.R.color.holo_blue_light)",
     "r.getColor(R.color.drag_outline_color)",
     marker="r.getColor(R.color.drag_outline_color)",
     desc="outline de arrasto (r)", count=0)

# 4) HolographicViewHelper ----------------------------------------------------------------
hv = SRC / "HolographicViewHelper.java"
edit(hv, "mHighlightColor = res.getColor(android.R.color.holo_blue_light);",
     "mHighlightColor = res.getColor(R.color.workspace_item_pressed_outline_color);",
     marker="R.color.workspace_item_pressed_outline_color", desc="cor de destaque")
edit(hv, "import android.view.View;\n",
     "import android.view.View;\n\nimport com.android.launcher.R;\n",
     marker="import com.android.launcher.R;", desc="import R")

# 5) user_folder.xml ----------------------------------------------------------------------
edit(RES / "layout/user_folder.xml", 'android:textColor="#ff33b5e5"',
     'android:textColor="#ff6595f9"', marker='android:textColor="#ff6595f9"',
     desc="nome da pasta")

# 6) drawables ----------------------------------------------------------------------------
for rel, b64 in ASSETS.items():
    data = base64.b64decode(b64)
    dst = RES / rel
    if not (dst.exists() and dst.read_bytes() == data):
        if not DRY:
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(data)
        CHANGED.append("drawable " + rel)
    # remove a versao xhdpi do ICS (o A35 usa xhdpi)
    x = RES / "drawable-xhdpi" / Path(rel).name
    if x.exists() and "drawable-xhdpi" not in rel:
        if not DRY:
            x.unlink()
        CHANGED.append("removido drawable-xhdpi/" + x.name + " (ICS)")

print("== 09: cores Honeycomb ==" + ("  (dry-run)" if DRY else ""))
for c in CHANGED:
    print("  ok  ", c)
if not CHANGED and not WARN:
    print("  nada a fazer (ja aplicado)")
if WARN:
    print("AVISOS:")
    for w in WARN:
        print("  !!  ", w)
    sys.exit(1)
