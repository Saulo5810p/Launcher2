#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
04b_canvas_cliptable_fix.py - corrige os erros de compilacao atuais do Launcher2 (SDK 34)

Rode na RAIZ do repositorio:   python3 04b_canvas_cliptable_fix.py [--dry-run]

1) Canvas.MATRIX_SAVE_FLAG / CLIP_SAVE_FLAG / ALL_SAVE_FLAG nao existem mais no SDK publico
   (DragLayer.java:542, BubbleTextView.java:293, CellLayout.java:484)
   -> canvas.save()   (salva matriz + clip; o restore() fica equivalente)

2) TableMaskFilter (brilho dos icones ao pressionar, glow do holographic outline)
   Continua tentando a classe oculta por reflexao. Se o Android bloquear (ou a classe sumir),
   aplica a MESMA tabela de clip em Java puro, direto nos pixels do bitmap ALPHA_8.
   Nao precisa de root: a restricao de APIs ocultas e' do processo do app, e o fallback
   reproduz o resultado visual sem depender dela.

Idempotente. Pontos nao encontrados sao listados no final como AVISO.
"""
import re
import sys
from pathlib import Path

SRC = Path("src/com/android/launcher2")
DRY = "--dry-run" in sys.argv
CHANGED, WARN = [], []


def rd(p):
    return p.read_text(encoding="utf-8")


def wr(p, t):
    if not DRY:
        p.write_text(t, encoding="utf-8")


def sub(fname, old, new, marker, desc):
    """Troca 'old' por 'new' em SRC/fname. 'marker' presente => ja aplicado."""
    p = SRC / fname
    if not p.exists():
        WARN.append(f"{fname}: {desc} (arquivo inexistente)")
        return
    t = rd(p)
    if marker in t:
        return
    if old not in t:
        WARN.append(f"{fname}: {desc} (trecho nao encontrado)")
        return
    wr(p, t.replace(old, new, 1))
    CHANGED.append(f"{fname}: {desc}")


# ---------------------------------------------------------------- 1) save flags
FLAG_RE = re.compile(
    r"\.save\(\s*(?:android\.graphics\.)?Canvas\.(?:MATRIX|CLIP|ALL)_SAVE_FLAG\s*\)")
for p in sorted(SRC.glob("*.java")):
    t = rd(p)
    new, n = FLAG_RE.subn(".save()", t)
    if n:
        wr(p, new)
        CHANGED.append(f"{p.name}: {n}x Canvas.*_SAVE_FLAG -> save()")

# ---------------------------------------------------------------- 2) clip table
HELPER = '''
    private static Boolean sClipTableAvailable;

    /** true se o TableMaskFilter oculto pode ser usado neste aparelho. */
    static synchronized boolean hasClipTable() {
        if (sClipTableAvailable == null) {
            sClipTableAvailable = createClipTable(0, 255) != null;
        }
        return sClipTableAvailable;
    }

    /**
     * Fallback em Java puro do TableMaskFilter.CreateClipTable(min, max): aplica, nos pixels de
     * um bitmap ALPHA_8 mutavel, a mesma tabela do Skia (SkTableMaskFilter::MakeClipTable).
     */
    static void applyClipTable(android.graphics.Bitmap mask, int min, int max) {
        if (mask == null || mask.getConfig() != android.graphics.Bitmap.Config.ALPHA_8
                || !mask.isMutable()) {
            return;
        }
        if (max == 0) max = 1;
        if (min >= max) min = max - 1;
        final byte[] lut = new byte[256];
        final float scale = 255.0f / (max - min);
        for (int i = 0; i < 256; i++) {
            int v;
            if (i <= min) v = 0;
            else if (i >= max) v = 255;
            else v = Math.round(scale * (i - min));
            lut[i] = (byte) v;
        }
        final java.nio.ByteBuffer buf = java.nio.ByteBuffer.allocate(mask.getByteCount());
        mask.copyPixelsToBuffer(buf);
        final byte[] px = buf.array();
        for (int i = 0; i < px.length; i++) {
            px[i] = lut[px[i] & 0xff];
        }
        buf.rewind();
        mask.copyPixelsFromBuffer(buf);
    }
'''

sub("Utilities.java",
    "    /** Android 13+ exige informar a flag de exportacao",
    HELPER + "\n    /** Android 13+ exige informar a flag de exportacao",
    "static void applyClipTable(", "helpers hasClipTable/applyClipTable")

# brilho ao pressionar / focar o icone
sub("Utilities.java",
    "            Bitmap mask = src.extractAlpha(sBlurPaint, xy);\n",
    "            Bitmap mask = src.extractAlpha(sBlurPaint, xy);\n"
    "            if (!hasClipTable()) {\n"
    "                applyClipTable(mask, 0, 30);   // fallback do TableMaskFilter\n"
    "            }\n",
    "applyClipTable(mask, 0, 30)", "brilho pressed/focused")

# holographic: glow das paginas
sub("HolographicOutlineHelper.java",
    "        Bitmap glow = bitmap.extractAlpha(mBlurPaint, mTempOffset);\n",
    "        Bitmap glow = bitmap.extractAlpha(mBlurPaint, mTempOffset);\n"
    "        if (!Utilities.hasClipTable()) {\n"
    "            Utilities.applyClipTable(glow, 0, 200);   // fallback do TableMaskFilter\n"
    "        }\n",
    "applyClipTable(glow, 0, 200)", "applyOuterBlur")

# holographic: contorno caro (so a tabela padrao 180..255; a (0,255) do widget e' identidade)
sub("HolographicOutlineHelper.java",
    "        if (alphaClipPaint == null) {\n            alphaClipPaint = mAlphaClipPaint;\n        }\n"
    "        Bitmap glowShape = srcDst.extractAlpha(alphaClipPaint, mTempOffset);\n",
    "        final boolean useDefaultClip = (alphaClipPaint == null);\n"
    "        if (alphaClipPaint == null) {\n            alphaClipPaint = mAlphaClipPaint;\n        }\n"
    "        Bitmap glowShape = srcDst.extractAlpha(alphaClipPaint, mTempOffset);\n"
    "        if (useDefaultClip && !Utilities.hasClipTable()) {\n"
    "            Utilities.applyClipTable(glowShape, 180, 255);   // fallback do TableMaskFilter\n"
    "        }\n",
    "useDefaultClip", "applyExpensiveOutlineWithBlur")

# ---------------------------------------------------------------- resumo
print("== 04b: canvas flags + clip table ==" + ("  (dry-run)" if DRY else ""))
for c in CHANGED:
    print("  ok  ", c)
if not CHANGED and not WARN:
    print("  nada a fazer (ja aplicado)")
if WARN:
    print("AVISOS:")
    for w in WARN:
        print("  !!  ", w)
