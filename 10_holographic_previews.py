#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
10_holographic_previews.py - preview HOLOGRAFICO de icones e widgets da gaveta (estilo Honeycomb)

Rode na RAIZ do repo (depois do 09):  python3 10_holographic_previews.py [--dry-run]  (idempotente)

DIAGNOSTICO (confirmado no codigo)
  O ICS DESLIGOU o efeito: AppsCustomizePagedView tem dois blocos
  "TEMPORARILY DISABLE HOLOGRAPHIC ICONS" comentados; alem disso (a) o PagedViewCellLayout do
  ICS nao tem a camada holografica que o Honeycomb tem (mHolographicChildren), (b) o contorno
  nunca era gerado de verdade (a tarefa so copiava o bitmap, sem blur/contorno), e (c) o
  PagedViewGridLayout (widgets) nao repassa o alpha da pagina aos widgets.

COMO O HONEYCOMB FAZ (portado do APK)
  * PagedViewCellLayout tem DUAS camadas: icones normais + camada holografica. setAlpha(a)
    aplica a nos icones e (1 - a) na camada holografica. Ao arrastar/rolar a gaveta, as paginas
    vizinhas "viram" contorno azul brilhante; na pagina centrada so aparece o icone normal.
  * Cada PagedViewIcon gera seu contorno (blur grosso + linha) numa thread de fundo, com cache,
    usando blurColor/outlineColor do XML (#6b8cf0 / #8cd2ff, ja identicos aos do Honeycomb).
  * Widgets: o preview ganha contorno holografico do mesmo jeito.

O QUE ESTE SCRIPT FAZ
  1. NOVO HolographicOutlineWorker.java: thread unica de fundo + cache LRU de contornos.
  2. PagedViewCellLayout: camada holografica (alpha invertido, hardware layers, gaps, add/remove).
  3. PagedViewIcon: le blurColor/outlineColor e pede o contorno (com cache) ao aplicar o app.
  4. HolographicPagedViewIcon: usa o padding do icone original (alinhamento exato).
  5. PagedViewWidget: le as cores e gera o contorno do preview quando ele carrega.
  6. PagedViewGridLayout: setAlpha repassa o alpha aos widgets (holografico ligado ao scroll).
  Os blocos "TEMPORARILY DISABLE" continuam comentados DE PROPOSITO: eles so copiavam o bitmap
  e sobrescreveriam o contorno real gerado aqui.
Pontos nao encontrados sao listados no final como AVISO (exit 1).
"""
import sys
from pathlib import Path

DRY = "--dry-run" in sys.argv
SRC = Path("src/com/android/launcher2")
CHANGED, WARN = [], []


def rd(p):
    return Path(p).read_text(encoding="utf-8")


def wr(p, t):
    if not DRY:
        Path(p).write_text(t, encoding="utf-8")


def edit(path, old, new, marker, desc):
    p = Path(path)
    tag = f"{p.name}: {desc}"
    if not p.exists():
        WARN.append(tag + " (arquivo inexistente)")
        return
    t = rd(p)
    if marker in t:
        return
    if t.count(old) != 1:
        WARN.append(tag + f" (trecho encontrado {t.count(old)}x, esperado 1x)")
        return
    wr(p, t.replace(old, new, 1))
    CHANGED.append(tag)


# ---------------------------------------------------------------------------------------
# 1) HolographicOutlineWorker (arquivo novo)
# ---------------------------------------------------------------------------------------
WORKER = '''/*
 * [10] Gera contornos holograficos (blur + linha, estilo Launcher2 Honeycomb) numa thread de
 * fundo unica e guarda os resultados num cache LRU. Portado do PagedViewIcon/PagedViewWidget
 * do Honeycomb, centralizado aqui.
 */
package com.android.launcher2;

import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.os.Handler;
import android.os.HandlerThread;
import android.os.Looper;
import android.os.Process;
import android.util.Log;

import java.util.LinkedHashMap;
import java.util.Map;

final class HolographicOutlineWorker {
    private static final String TAG = "HolographicOutlineWorker";
    private static final int CACHE_MAX = 160;

    interface Callback {
        /** Chamado na thread principal. */
        void onOutline(Bitmap outline);
    }

    private static Handler sWorker;
    private static Handler sMain;
    private static HolographicOutlineHelper sHelper; // usado so na thread de fundo

    private static final LinkedHashMap<String, Bitmap> sCache =
            new LinkedHashMap<String, Bitmap>(32, 0.75f, true) {
                @Override
                protected boolean removeEldestEntry(Map.Entry<String, Bitmap> eldest) {
                    return size() > CACHE_MAX;
                }
            };

    private HolographicOutlineWorker() {}

    static Bitmap getCached(String key) {
        if (key == null) return null;
        synchronized (sCache) {
            return sCache.get(key);
        }
    }

    private static synchronized void ensureStarted() {
        if (sWorker == null) {
            HandlerThread t = new HandlerThread("holographic-outline",
                    Process.THREAD_PRIORITY_BACKGROUND);
            t.start();
            sWorker = new Handler(t.getLooper());
            sMain = new Handler(Looper.getMainLooper());
        }
    }

    /**
     * Pede um contorno para "src" (o bitmap NAO e modificado). Se "key" != null o resultado
     * entra no cache. "src" nao pode ser reciclado enquanto a tarefa roda (passe uma copia se
     * o dono puder recicla-lo).
     */
    static void request(final Bitmap src, final String key, final int blurColor,
            final int outlineColor, final Callback cb) {
        if (src == null || src.isRecycled()) return;
        ensureStarted();
        sWorker.post(new Runnable() {
            @Override
            public void run() {
                try {
                    if (src.isRecycled()) return;
                    if (sHelper == null) sHelper = new HolographicOutlineHelper();
                    final Bitmap out = Bitmap.createBitmap(src.getWidth(), src.getHeight(),
                            Bitmap.Config.ARGB_8888);
                    Canvas c = new Canvas(out);
                    c.drawBitmap(src, 0, 0, null);
                    sHelper.applyThickExpensiveOutlineWithBlur(out, c, blurColor, outlineColor);
                    if (key != null) {
                        synchronized (sCache) {
                            sCache.put(key, out);
                        }
                    }
                    if (cb != null) {
                        sMain.post(new Runnable() {
                            @Override
                            public void run() {
                                cb.onOutline(out);
                            }
                        });
                    }
                } catch (Throwable t) {
                    Log.w(TAG, "falha ao gerar contorno holografico", t);
                }
            }
        });
    }
}
'''
wp = SRC / "HolographicOutlineWorker.java"
if wp.exists():
    if rd(wp) != WORKER:
        WARN.append("HolographicOutlineWorker.java: ja existe com conteudo diferente (nao sobrescrito)")
else:
    wr(wp, WORKER)
    CHANGED.append("HolographicOutlineWorker.java: criado")

# ---------------------------------------------------------------------------------------
# 2) PagedViewCellLayout: camada holografica
# ---------------------------------------------------------------------------------------
PCL = SRC / "PagedViewCellLayout.java"
M = "mHolographicChildren"
edit(PCL, "    protected PagedViewCellLayoutChildren mChildren;\n",
     "    protected PagedViewCellLayoutChildren mChildren;\n"
     "    // [10] camada holografica (alpha = 1 - alpha dos icones), como no Honeycomb\n"
     "    protected PagedViewCellLayoutChildren mHolographicChildren;\n",
     marker="protected PagedViewCellLayoutChildren mHolographicChildren", desc="campo")
edit(PCL, "        mChildren.setGap(mWidthGap, mHeightGap);\n\n        addView(mChildren);\n    }",
     "        mChildren.setGap(mWidthGap, mHeightGap);\n\n        addView(mChildren);\n\n"
     "        // [10] camada holografica\n"
     "        mHolographicChildren = new PagedViewCellLayoutChildren(context);\n"
     "        mHolographicChildren.setAlpha(0.0f);\n"
     "        mHolographicChildren.setCellDimensions(mCellWidth, mCellHeight);\n"
     "        mHolographicChildren.setGap(mWidthGap, mHeightGap);\n"
     "        addView(mHolographicChildren);\n    }",
     marker="mHolographicChildren = new PagedViewCellLayoutChildren", desc="construtor")
edit(PCL, "        mChildren.setAlpha(alpha);\n    }",
     "        mChildren.setAlpha(alpha);\n"
     "        mHolographicChildren.setAlpha(1.0f - alpha); // [10]\n    }",
     marker="mHolographicChildren.setAlpha(1.0f - alpha)", desc="setAlpha")
edit(PCL, "        mChildren.destroyHardwareLayer();\n    }",
     "        mChildren.destroyHardwareLayer();\n"
     "        mHolographicChildren.destroyHardwareLayer(); // [10]\n    }",
     marker="mHolographicChildren.destroyHardwareLayer()", desc="destroyHardwareLayers")
edit(PCL, "        mChildren.createHardwareLayer();\n    }",
     "        mChildren.createHardwareLayer();\n"
     "        mHolographicChildren.createHardwareLayer(); // [10]\n    }",
     marker="mHolographicChildren.createHardwareLayer()", desc="createHardwareLayers")
edit(PCL, "                pagedViewIcon.disableCache();\n            }",
     "                pagedViewIcon.disableCache();\n"
     "                // [10] contorno holografico do icone na camada de cima\n"
     "                mHolographicChildren.addView(pagedViewIcon.getHolographicOutlineView(),\n"
     "                        index, lp);\n            }",
     marker="mHolographicChildren.addView(", desc="addViewToCellLayout")
edit(PCL, "        mChildren.removeAllViews();\n        destroyHardwareLayers();",
     "        mChildren.removeAllViews();\n"
     "        mHolographicChildren.removeAllViews(); // [10]\n        destroyHardwareLayers();",
     marker="mHolographicChildren.removeAllViews()", desc="removeAllViewsOnPage")
edit(PCL, "        mChildren.removeViewAt(index);\n    }",
     "        mChildren.removeViewAt(index);\n"
     "        mHolographicChildren.removeViewAt(index); // [10]\n    }",
     marker="mHolographicChildren.removeViewAt(index)", desc="removeViewOnPageAt")
edit(PCL, "            mChildren.setGap(mWidthGap, mHeightGap);\n        } else {",
     "            mChildren.setGap(mWidthGap, mHeightGap);\n"
     "            mHolographicChildren.setGap(mWidthGap, mHeightGap); // [10]\n        } else {",
     marker="mHolographicChildren.setGap(mWidthGap, mHeightGap); // [10]", desc="onMeasure gaps")
edit(PCL, "        mChildren.enableCenteredContent(enabled);",
     "        mChildren.enableCenteredContent(enabled);\n"
     "        mHolographicChildren.enableCenteredContent(enabled); // [10]",
     marker="mHolographicChildren.enableCenteredContent", desc="enableCenteredContent")
edit(PCL, "        mChildren.setChildrenDrawingCacheEnabled(enabled);",
     "        mChildren.setChildrenDrawingCacheEnabled(enabled);\n"
     "        mHolographicChildren.setChildrenDrawingCacheEnabled(enabled); // [10]",
     marker="mHolographicChildren.setChildrenDrawingCacheEnabled", desc="drawingCache")
edit(PCL, "        mChildren.setGap(widthGap, heightGap);",
     "        mChildren.setGap(widthGap, heightGap);\n"
     "        mHolographicChildren.setGap(widthGap, heightGap); // [10]",
     marker="mHolographicChildren.setGap(widthGap, heightGap)", desc="setGap")

# ---------------------------------------------------------------------------------------
# 3) PagedViewIcon: cores + contorno com cache
# ---------------------------------------------------------------------------------------
PVI = SRC / "PagedViewIcon.java"
edit(PVI, "    private int mAlpha = 255;\n",
     "    private int mAlpha = 255;\n"
     "    // [10] cores do contorno holografico (blurColor / outlineColor do XML)\n"
     "    private int mHoloBlurColor;\n"
     "    private int mHoloOutlineColor;\n",
     marker="private int mHoloBlurColor;", desc="campos de cor")
edit(PVI, "        mHolographicOutlineView = new HolographicPagedViewIcon(context, this);\n    }",
     "        mHolographicOutlineView = new HolographicPagedViewIcon(context, this);\n\n"
     "        // [10]\n"
     "        TypedArray a = context.obtainStyledAttributes(attrs, R.styleable.PagedViewIcon,\n"
     "                defStyle, 0);\n"
     "        mHoloBlurColor = a.getColor(R.styleable.PagedViewIcon_blurColor, 0xFF6B8CF0);\n"
     "        mHoloOutlineColor = a.getColor(R.styleable.PagedViewIcon_outlineColor, 0xFF8CD2FF);\n"
     "        a.recycle();\n    }",
     marker="R.styleable.PagedViewIcon_blurColor", desc="le atributos")
edit(PVI, "        setTag(info);\n",
     "        setTag(info);\n\n"
     "        // [10] contorno holografico (cache + thread de fundo)\n"
     "        final Bitmap iconSrc = mIcon;\n"
     "        final String key = (info.componentName != null\n"
     "                ? info.componentName.flattenToString() : String.valueOf(info.title))\n"
     "                + \"#\" + System.identityHashCode(iconSrc);\n"
     "        Bitmap cached = HolographicOutlineWorker.getCached(key);\n"
     "        if (cached != null) {\n"
     "            setHolographicOutline(cached);\n"
     "        } else if (iconSrc != null) {\n"
     "            HolographicOutlineWorker.request(iconSrc, key, mHoloBlurColor, mHoloOutlineColor,\n"
     "                    new HolographicOutlineWorker.Callback() {\n"
     "                        @Override\n"
     "                        public void onOutline(Bitmap outline) {\n"
     "                            if (mIcon == iconSrc) setHolographicOutline(outline);\n"
     "                        }\n"
     "                    });\n"
     "        }\n",
     marker="HolographicOutlineWorker.getCached(key)", desc="gera contorno")

# ---------------------------------------------------------------------------------------
# 4) HolographicPagedViewIcon: alinhamento com o icone original
# ---------------------------------------------------------------------------------------
edit(SRC / "HolographicPagedViewIcon.java",
     "            final int compoundPaddingLeft = getCompoundPaddingLeft();\n"
     "            final int compoundPaddingRight = getCompoundPaddingRight();\n",
     "            // [10] mesmo padding do icone original\n"
     "            final int compoundPaddingLeft = mOriginalIcon.getCompoundPaddingLeft();\n"
     "            final int compoundPaddingRight = mOriginalIcon.getCompoundPaddingRight();\n",
     marker="mOriginalIcon.getCompoundPaddingLeft()", desc="padding do original")

# ---------------------------------------------------------------------------------------
# 5) PagedViewWidget: cores + contorno do preview
# ---------------------------------------------------------------------------------------
PVW = SRC / "PagedViewWidget.java"
edit(PVW, "import android.content.res.Resources;\n",
     "import android.content.res.Resources;\nimport android.content.res.TypedArray;\n",
     marker="import android.content.res.TypedArray;", desc="import TypedArray")
edit(PVW, "    private int mAlpha = 255;\n",
     "    private int mAlpha = 255;\n"
     "    // [10] cores do contorno holografico\n"
     "    private int mHoloBlurColor = 0xFF6B8CF0;\n"
     "    private int mHoloOutlineColor = 0xFF8CD2FF;\n",
     marker="private int mHoloBlurColor", desc="campos de cor")
edit(PVW, "        mDimensionsFormatString = r.getString(R.string.widget_dims_format);\n",
     "        mDimensionsFormatString = r.getString(R.string.widget_dims_format);\n\n"
     "        // [10]\n"
     "        TypedArray a = context.obtainStyledAttributes(attrs, R.styleable.PagedViewWidget,\n"
     "                defStyle, 0);\n"
     "        mHoloBlurColor = a.getColor(R.styleable.PagedViewWidget_blurColor, mHoloBlurColor);\n"
     "        mHoloOutlineColor = a.getColor(R.styleable.PagedViewWidget_outlineColor,\n"
     "                mHoloOutlineColor);\n"
     "        a.recycle();\n",
     marker="R.styleable.PagedViewWidget_blurColor", desc="le atributos")
edit(PVW, "            image.setImageDrawable(preview);\n",
     "            image.setImageDrawable(preview);\n"
     "            // [10] contorno holografico do preview (copia: o original pode ser reciclado)\n"
     "            final Bitmap previewBitmap = preview.getBitmap();\n"
     "            if (previewBitmap != null && !previewBitmap.isRecycled()) {\n"
     "                final Bitmap copy = previewBitmap.copy(Bitmap.Config.ARGB_8888, false);\n"
     "                if (copy != null) {\n"
     "                    HolographicOutlineWorker.request(copy, null, mHoloBlurColor,\n"
     "                            mHoloOutlineColor, new HolographicOutlineWorker.Callback() {\n"
     "                                @Override\n"
     "                                public void onOutline(Bitmap outline) {\n"
     "                                    setHolographicOutline(outline);\n"
     "                                }\n"
     "                            });\n"
     "                }\n"
     "            }\n",
     marker="contorno holografico do preview", desc="gera contorno do preview")

# ---------------------------------------------------------------------------------------
# 6) PagedViewGridLayout: alpha da pagina chega aos widgets
# ---------------------------------------------------------------------------------------
edit(SRC / "PagedViewGridLayout.java",
     "    void destroyHardwareLayer() {\n",
     "    // [10] o alpha da pagina vai para cada widget (PagedViewWidget.setAlpha separa em\n"
     "    // alpha do widget + alpha do contorno holografico, como o PagedViewCellLayout)\n"
     "    @Override\n"
     "    public void setAlpha(float alpha) {\n"
     "        final int count = getChildCount();\n"
     "        for (int i = 0; i < count; i++) {\n"
     "            getChildAt(i).setAlpha(alpha);\n"
     "        }\n"
     "    }\n\n"
     "    void destroyHardwareLayer() {\n",
     marker="o alpha da pagina vai para cada widget", desc="setAlpha repassa aos widgets")

# ---------------------------------------------------------------------------------------
print("== 10: preview holografico ==" + ("  (dry-run)" if DRY else ""))
for c in CHANGED:
    print("  ok  ", c)
if not CHANGED and not WARN:
    print("  nada a fazer (ja aplicado)")
if WARN:
    print("AVISOS:")
    for w in WARN:
        print("  !!  ", w)
    sys.exit(1)