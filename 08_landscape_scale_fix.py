#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""08_landscape_scale_fix.py - gaveta (icones e widgets) com escala correta em paisagem.
Rode na RAIZ do repo: python3 08_landscape_scale_fix.py [--dry-run]  (idempotente)"""
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
    if old not in t:
        WARN.append(tag + " (trecho nao encontrado)")
        return
    wr(p, t.replace(old, new, 1))
    CHANGED.append(tag)

APC = SRC / "AppsCustomizePagedView.java"

edit(APC,
     "    private int mContentWidth;\n",
     "    private int mContentWidth;\n"
     "    // [08] tamanho com que a grade (colunas/linhas/widgets) foi calculada pela ultima vez\n"
     "    private int mReadyWidth = -1;\n"
     "    private int mReadyHeight = -1;\n",
     marker="mReadyWidth = -1", desc="campos do tamanho da ultima grade")

edit(APC,
     "        mWidgetSpacingLayout.setGap(mPageLayoutWidthGap, mPageLayoutHeightGap);\n"
     "        mWidgetSpacingLayout.setPadding(mPageLayoutPaddingLeft, mPageLayoutPaddingTop,\n"
     "                mPageLayoutPaddingRight, mPageLayoutPaddingBottom);\n"
     "        mWidgetSpacingLayout.calculateCellCount(width, height, maxCellCountX, maxCellCountY);\n",
     "        // [08] widgetCountX/Y dependem da orientacao (values-land): relê a cada calculo\n"
     "        mWidgetCountX = Math.max(1,\n"
     "                getResources().getInteger(R.integer.apps_customize_widget_cell_count_x));\n"
     "        mWidgetCountY = Math.max(1,\n"
     "                getResources().getInteger(R.integer.apps_customize_widget_cell_count_y));\n"
     "        mReadyWidth = width;\n"
     "        mReadyHeight = height;\n"
     "\n"
     "        mWidgetSpacingLayout.setGap(mPageLayoutWidthGap, mPageLayoutHeightGap);\n"
     "        mWidgetSpacingLayout.setPadding(mPageLayoutPaddingLeft, mPageLayoutPaddingTop,\n"
     "                mPageLayoutPaddingRight, mPageLayoutPaddingBottom);\n"
     "        mWidgetSpacingLayout.calculateCellCount(width, height, maxCellCountX, maxCellCountY);\n",
     marker="[08] widgetCountX/Y dependem da orientacao", desc="onDataReady relê widgetCountX/Y")

edit(APC,
     "        int width = MeasureSpec.getSize(widthMeasureSpec);\n"
     "        int height = MeasureSpec.getSize(heightMeasureSpec);\n"
     "        if (!isDataReady()) {\n",
     "        int width = MeasureSpec.getSize(widthMeasureSpec);\n"
     "        int height = MeasureSpec.getSize(heightMeasureSpec);\n"
     "        // [08] O tamanho mudou desde que a grade foi calculada (rotacao): refaz a grade\n"
     "        // com o tamanho NOVO, voltando para a mesma pagina.\n"
     "        if (isDataReady() && width > 0 && height > 0 && mReadyWidth > 0\n"
     "                && (width != mReadyWidth || height != mReadyHeight)) {\n"
     "            int keep = getSaveInstanceStateIndex();\n"
     "            if (keep >= 0) mSaveInstanceStateItemIndex = keep;\n"
     "            mIsDataReady = false;\n"
     "        }\n"
     "        if (!isDataReady()) {\n",
     marker="[08] O tamanho mudou", desc="onMeasure detecta mudanca de tamanho")

edit(SRC / "AppsCustomizeTabHost.java",
     "        boolean remeasureTabWidth = (mTabs.getLayoutParams().width <= 0);\n"
     "        super.onMeasure(widthMeasureSpec, heightMeasureSpec);\n"
     "\n"
     "        // Set the width of the tab list to the content width\n"
     "        if (remeasureTabWidth) {\n"
     "            int contentWidth = mAppsCustomizePane.getPageContentWidth();\n"
     "            if (contentWidth > 0) {\n",
     "        super.onMeasure(widthMeasureSpec, heightMeasureSpec);\n"
     "\n"
     "        // Set the width of the tab list to the content width\n"
     "        // [08] refeito a cada mudanca da largura do conteudo (rotacao), nao so na 1a vez\n"
     "        {\n"
     "            int contentWidth = mAppsCustomizePane.getPageContentWidth();\n"
     "            if (contentWidth > 0 && mTabs.getLayoutParams().width != contentWidth) {\n",
     marker="[08] refeito a cada mudanca", desc="largura das abas acompanha o conteudo")

edit(SRC / "PagedViewCellLayout.java",
     "            mWidthGap = Math.min(mMaxGap, numWidthGaps > 0 ? (hFreeSpace / numWidthGaps) : 0);\n"
     "            mHeightGap = Math.min(mMaxGap,numHeightGaps > 0 ? (vFreeSpace / numHeightGaps) : 0);\n",
     "            // [08] gap negativo = celulas sobrepostas; nunca abaixo de 0\n"
     "            mWidthGap = Math.max(0, Math.min(mMaxGap,\n"
     "                    numWidthGaps > 0 ? (hFreeSpace / numWidthGaps) : 0));\n"
     "            mHeightGap = Math.max(0, Math.min(mMaxGap,\n"
     "                    numHeightGaps > 0 ? (vFreeSpace / numHeightGaps) : 0));\n",
     marker="[08] gap negativo", desc="gaps >= 0")

print("== 08: escala da gaveta em paisagem ==" + ("  (dry-run)" if DRY else ""))
for c in CHANGED:
    print("  ok  ", c)
if not CHANGED and not WARN:
    print("  nada a fazer (ja aplicado)")
if WARN:
    print("AVISOS:")
    for w in WARN:
        print("  !!  ", w)
    sys.exit(1)