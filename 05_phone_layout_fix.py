#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
05_phone_layout_fix.py - Launcher2 (ICS, layout tablet) -> grade que se adapta ao CELULAR

Rode na RAIZ do repositorio (depois dos scripts 01..04b):
    python3 05_phone_layout_fix.py [--dry-run]

Causa do layout espremido
-------------------------
Workspace.java comparava `smallestScreenWidthDp` (DP) com `CellLayout.widthInPortrait()` (PIXELS).
No Galaxy A35 (densidade 2.81, sw384dp) cada celula de 96dp vira 270px, entao a conta dava
1 coluna x 1 linha. Isso explica tudo:
  * paginas minusculas; * gaveta com 1 icone por pagina (o limite vem dessa grade);
  * abas espremidas (a largura das abas = largura do conteudo = 1 celula);
  * LauncherModel "Desktop items loading interrupted: ArrayIndexOutOfBounds" (itens fora da 1x1);
  * widgets: previews com largura/altura 0 -> "width and height must be > 0".
(O valor que importa e' a largura minima em DP = 384, ja considerando a densidade: 1080px / 2.8125.
 A densidade so converte dp<->px; o layout inteiro e' escrito em dp.)

O que este script faz
---------------------
1. Grade do workspace calculada em DP (4 colunas x 4 linhas no A35). Para forcar outra grade
   edite res/values/config.xml: workspace_cell_count_x / workspace_cell_count_y (0 = automatico).
2. As paginas do workspace passam a PREENCHER o espaco entre a barra de busca/microfone/gaveta
   e a barra de navegacao: as celulas sao esticadas (CellLayout fillAvailable).
3. Gaveta: sem limite de colunas/linhas herdado da grade do workspace; celulas menores; abas e
   botao "Comprar" com fonte/padding de celular.
4. Gaveta translucida: o wallpaper aparece com escurecimento leve (cor apps_customize_bg_color
   em res/values/colors.xml, #B3080808 = 70%; menor alpha = mais wallpaper).
5. Widgets: getWidgetPreview nunca cria Bitmap com largura/altura <= 0.
6. LauncherModel ignora (sem estourar) itens salvos fora da grade atual.
7. Icones em 48dp (os 72dp do tablet sao grandes demais para celular; ver DIMENS no script).

Idempotente. Pontos nao encontrados sao listados no final como AVISO.
"""
import re
import sys
from pathlib import Path

DRY = "--dry-run" in sys.argv
SRC = Path("src/com/android/launcher2")
RES = Path("res")
CHANGED, WARN = [], []


def rd(p):
    return p.read_text(encoding="utf-8")


def wr(p, t):
    if not DRY:
        p.write_text(t, encoding="utf-8")


def edit(path, old, new, marker=None, desc=None, count=1):
    """Troca 'old' por 'new'. 'marker' (texto que so existe depois da edicao) => ja aplicado."""
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
    wr(p, t.replace(old, new, count))
    CHANGED.append(tag)


# ------------------------------------------------------------------ 1) dimens
DIMENS = {
    "app_icon_size": "48dp",       # cabe em celulas de ~67dp (paisagem do A35); suba para 56dp se preferir
    "workspace_page_spacing": "0dp",
    "workspace_content_large_only_top_margin": "56dp",   # = altura da barra de busca (qsb_bar_height)
    "workspace_left_padding": "6dp",
    "workspace_right_padding": "6dp",
    "workspace_top_padding": "4dp",
    "workspace_bottom_padding": "8dp",
    "workspace_width_gap": "0dp",
    "workspace_height_gap": "0dp",
    "workspace_cell_width": "80dp",       # so valem antes da 1a medida (as celulas sao esticadas)
    "workspace_cell_height": "80dp",
    "apps_customize_cell_width": "80dp",
    "apps_customize_cell_height": "96dp",
    "apps_customize_max_gap": "12dp",
    "apps_customize_pageLayoutWidthGap": "8dp",
    "apps_customize_pageLayoutHeightGap": "8dp",
    "apps_customize_pageLayoutPaddingTop": "12dp",
    "apps_customize_pageLayoutPaddingBottom": "16dp",
    "apps_customize_pageLayoutPaddingLeft": "8dp",
    "apps_customize_pageLayoutPaddingRight": "8dp",
    "apps_customize_widget_cell_width_gap": "12dp",
    "apps_customize_widget_cell_height_gap": "12dp",
    "apps_customize_tab_bar_height": "48dp",
}
# values/ e values-land/ (a paisagem tinha paddings/gaps/espacamento de pagina proprios)
for p in (RES / "values/dimens.xml", RES / "values-land/dimens.xml"):
    if not p.exists():
        WARN.append(f"{p} inexistente")
        continue
    t = rd(p)
    orig = t
    for name, val in DIMENS.items():
        t = re.sub(r'(<dimen name="%s">)[^<]*(</dimen>)' % re.escape(name), r"\g<1>%s\g<2>" % val, t)
    if t != orig:
        wr(p, t)
        CHANGED.append(f"{p.parent.name}/dimens.xml: dimensoes para celular")

# ------------------------------------------------------------------ 2) config / attrs / colors
edit(RES / "values/config.xml", "</resources>",
     '    <!-- Grade do workspace. 0 = automatica (calculada em dp pelo Workspace). -->\n'
     '    <integer name="workspace_cell_count_x">0</integer>\n'
     '    <integer name="workspace_cell_count_y">0</integer>\n</resources>',
     marker="workspace_cell_count_x", desc="workspace_cell_count_x/y")

edit(RES / "values/attrs.xml",
     '<attr name="cellHeight" format="dimension" />',
     '<attr name="cellHeight" format="dimension" />\n'
     '        <!-- Estica as celulas para ocupar todo o espaco da pagina (celular) -->\n'
     '        <attr name="fillAvailable" format="boolean" />',
     marker='name="fillAvailable"', desc="attr fillAvailable")

edit(RES / "values/colors.xml", "</resources>",
     '    <!-- Fundo da gaveta de apps: wallpaper visivel com escurecimento (estilo Honeycomb) -->\n'
     '    <color name="apps_customize_bg_color">#B3080808</color>\n</resources>',
     marker="apps_customize_bg_color", desc="cor do fundo da gaveta")

edit(RES / "layout/workspace_screen.xml",
     'launcher:cellWidth="@dimen/workspace_cell_width"',
     'launcher:fillAvailable="true"\n    launcher:cellWidth="@dimen/workspace_cell_width"',
     marker="fillAvailable", desc="workspace_screen fillAvailable")

_pane = RES / "layout/apps_customize_pane.xml"
if not (_pane.exists() and "all_apps_bg_gradient" in rd(_pane)):   # o 07 usa o gradiente do Honeycomb
    edit(_pane,
         'android:background="#FF000000">',
         'android:background="@color/apps_customize_bg_color">',
         marker="apps_customize_bg_color", desc="gaveta translucida")

# abas / botao Comprar com tamanho de celular
p = RES / "values/styles.xml"
if p.exists():
    t = rd(p)
    o = t
    t = re.sub(r'(<style name="TabIndicator">.*?)<item name="android:paddingLeft">35dp</item>\s*'
               r'<item name="android:paddingRight">35dp</item>',
               r'\1<item name="android:paddingLeft">14dp</item>\n        '
               r'<item name="android:paddingRight">14dp</item>', t, flags=re.S)
    t = re.sub(r'(<style name="TabIndicator.AppsCustomize">)\s*<item name="android:paddingLeft">40dp</item>\s*'
               r'<item name="android:paddingRight">40dp</item>(.*?)<item name="android:textSize">20sp</item>',
               r'\1\n        <item name="android:paddingLeft">14dp</item>\n        '
               r'<item name="android:paddingRight">14dp</item>\2<item name="android:textSize">15sp</item>',
               t, flags=re.S)
    t = re.sub(r'(<style name="MarketButton">.*?)<item name="android:textSize">18sp</item>',
               r'\1<item name="android:textSize">15sp</item>', t, flags=re.S)
    if t != o:
        wr(p, t)
        CHANGED.append("styles.xml: abas e botao Comprar menores")
edit(RES / "layout/market_button.xml", 'android:textSize="18sp"', 'android:textSize="15sp"',
     desc="market_button 15sp")

# ------------------------------------------------------------------ 3) CellLayout
CL = SRC / "CellLayout.java"
edit(CL, "    private int mHeightGap;\n",
     "    private int mHeightGap;\n"
     "    // Celular: estica as celulas para ocupar toda a pagina (ver fillMeasure)\n"
     "    private boolean mFillAvailable;\n"
     "    // Tamanho real (px) das celulas do workspace; usado para calcular spans de widgets\n"
     "    static int sWorkspaceCellWidth = -1;\n"
     "    static int sWorkspaceCellHeight = -1;\n",
     marker="mFillAvailable;", desc="campos mFillAvailable")

edit(CL, "        mOccupied = new boolean[mCountX][mCountY];\n\n        a.recycle();",
     "        mOccupied = new boolean[mCountX][mCountY];\n"
     "        mFillAvailable = a.getBoolean(R.styleable.CellLayout_fillAvailable, false);\n\n"
     "        a.recycle();",
     marker="CellLayout_fillAvailable", desc="le fillAvailable")

FILL_METHOD = '''    /** Celular: divide a area da pagina em countX x countY celulas iguais (sem gaps). */
    private void fillMeasure(int widthSize, int heightSize) {
        final int hSpace = Math.max(1, widthSize - getPaddingLeft() - getPaddingRight());
        final int vSpace = Math.max(1, heightSize - getPaddingTop() - getPaddingBottom());
        mWidthGap = 0;
        mHeightGap = 0;
        mCellWidth = Math.max(1, hSpace / Math.max(1, mCountX));
        mCellHeight = Math.max(1, vSpace / Math.max(1, mCountY));
        sWorkspaceCellWidth = mCellWidth;
        sWorkspaceCellHeight = mCellHeight;
        mChildren.setCellDimensions(mCellWidth, mCellHeight, 0, 0);

        final int count = getChildCount();
        for (int i = 0; i < count; i++) {
            View child = getChildAt(i);
            child.measure(MeasureSpec.makeMeasureSpec(hSpace, MeasureSpec.EXACTLY),
                    MeasureSpec.makeMeasureSpec(vSpace, MeasureSpec.EXACTLY));
        }
        setMeasuredDimension(widthSize, heightSize);
    }

    static int workspaceCellWidth(Resources r) {
        return sWorkspaceCellWidth > 0 ? sWorkspaceCellWidth
                : r.getDimensionPixelSize(R.dimen.workspace_cell_width);
    }

    static int workspaceCellHeight(Resources r) {
        return sWorkspaceCellHeight > 0 ? sWorkspaceCellHeight
                : r.getDimensionPixelSize(R.dimen.workspace_cell_height);
    }

'''
edit(CL, "    @Override\n    protected void onMeasure(int widthMeasureSpec, int heightMeasureSpec) {\n"
         "        // TODO: currently ignoring padding\n",
     FILL_METHOD + "    @Override\n    protected void onMeasure(int widthMeasureSpec, int heightMeasureSpec) {\n"
                   "        // TODO: currently ignoring padding\n",
     marker="private void fillMeasure(", desc="metodo fillMeasure")

edit(CL, "        int numWidthGaps = mCountX - 1;\n        int numHeightGaps = mCountY - 1;\n\n"
         "        if (mOriginalWidthGap < 0 || mOriginalHeightGap < 0) {\n            int hSpace = widthSpecSize",
     "        if (mFillAvailable) {\n            fillMeasure(widthSpecSize, heightSpecSize);\n            return;\n        }\n\n"
     "        int numWidthGaps = mCountX - 1;\n        int numHeightGaps = mCountY - 1;\n\n"
     "        if (mOriginalWidthGap < 0 || mOriginalHeightGap < 0) {\n            int hSpace = widthSpecSize",
     marker="fillMeasure(widthSpecSize", desc="onMeasure usa fillMeasure")

edit(CL, "        int actualWidth = resources.getDimensionPixelSize(R.dimen.workspace_cell_width);\n"
         "        int actualHeight = resources.getDimensionPixelSize(R.dimen.workspace_cell_height);",
     "        int actualWidth = workspaceCellWidth(resources);\n"
     "        int actualHeight = workspaceCellHeight(resources);",
     marker="workspaceCellWidth(resources)", desc="rectToCell com celula real")

# ------------------------------------------------------------------ 4) Workspace
WS = SRC / "Workspace.java"
p = WS
if p.exists():
    t = rd(p)
    start = t.find("        if (LauncherApplication.isScreenLarge()) {\n            // Determine number of rows/columns dynamically")
    end = t.find("        mSpringLoadedShrinkFactor =")
    if "Grade para celular, calculada em DP" in t:
        pass
    elif start < 0 or end < 0 or end < start:
        WARN.append("Workspace.java: bloco de calculo da grade nao encontrado")
    else:
        NEW = '''        {
            // Grade para celular, calculada em DP (o original comparava dp com pixels e dava 1x1).
            // Mesma grade em retrato e paisagem: usa o lado menor da tela.
            final DisplayMetrics dm = res.getDisplayMetrics();
            final float shortDp = Math.min(dm.widthPixels, dm.heightPixels) / dm.density;
            final float topBarDp = res.getDimension(R.dimen.qsb_bar_height) / dm.density;
            cellCountX = Math.max(4, Math.round(shortDp / 88f));
            // linhas: o que cabe na altura da paisagem (lado menor - status bar - barra de busca)
            cellCountY = Math.max(4, Math.round((shortDp - 24f - topBarDp - 16f) / 76f));
            final int cfgX = res.getInteger(R.integer.workspace_cell_count_x);
            final int cfgY = res.getInteger(R.integer.workspace_cell_count_y);
            if (cfgX > 0) cellCountX = cfgX;
            if (cfgY > 0) cellCountY = cfgY;
        }

'''
        wr(p, t[:start] + NEW + t[end:])
        CHANGED.append("Workspace.java: grade calculada em dp")

edit(WS, "        final int iconWidth = r.getDimensionPixelSize(R.dimen.workspace_cell_width);\n"
         "        final int iconHeight = r.getDimensionPixelSize(R.dimen.workspace_cell_height);",
     "        final int iconWidth = CellLayout.workspaceCellWidth(r);\n"
     "        final int iconHeight = CellLayout.workspaceCellHeight(r);",
     marker="CellLayout.workspaceCellWidth(r)", desc="drag outline externo")

# ------------------------------------------------------------------ 5) Gaveta
PV = SRC / "AppsCustomizePagedView.java"
edit(PV, "        if (LauncherApplication.isScreenLarge()) {\n"
         "            maxCellCountX = (isLandscape ? LauncherModel.getCellCountX() :\n"
         "                LauncherModel.getCellCountY());\n"
         "            maxCellCountY = (isLandscape ? LauncherModel.getCellCountY() :\n"
         "                LauncherModel.getCellCountX());\n"
         "        }\n",
     "        // Celular: sem limite herdado da grade do workspace; o que cabe na tela decide.\n",
     marker="sem limite herdado da grade", desc="gaveta sem limite de grade")

edit(PV, "    @Override\n    protected void onMeasure(int widthMeasureSpec, int heightMeasureSpec) {\n"
         "        int width = MeasureSpec.getSize(widthMeasureSpec);",
     "    /** Rotacao/mudanca de tamanho: recalcula colunas e linhas da gaveta. */\n"
     "    void onConfigurationRefresh() {\n"
     "        mIsDataReady = false;\n"
     "        requestLayout();\n"
     "    }\n\n"
     "    @Override\n    protected void onMeasure(int widthMeasureSpec, int heightMeasureSpec) {\n"
     "        int width = MeasureSpec.getSize(widthMeasureSpec);",
     marker="void onConfigurationRefresh()", desc="onConfigurationRefresh")

edit(SRC / "PagedViewCellLayout.java",
     "        int availWidth = (int) (width - (2 * getPaddingLeft() + 2 * getPaddingRight()));",
     "        int availWidth = width - (getPaddingLeft() + getPaddingRight());",
     marker="int availWidth = width - (getPaddingLeft()", desc="estimateCellHSpan sem dobrar padding")

# ------------------------------------------------------------------ 6) crash dos widgets
edit(PV, "        // Load the preview image if possible\n        String packageName = info.provider.getPackageName();",
     "        cellWidth = Math.max(1, cellWidth);\n        cellHeight = Math.max(1, cellHeight);\n\n"
     "        // Load the preview image if possible\n        String packageName = info.provider.getPackageName();",
     marker="cellWidth = Math.max(1, cellWidth);", desc="getWidgetPreview: celula >= 1")

edit(PV, "                int imageHeight = drawable.getIntrinsicHeight();\n",
     "                int imageHeight = drawable.getIntrinsicHeight();\n"
     "                if (imageWidth <= 0 || imageHeight <= 0) {\n"
     "                    imageWidth = cellWidth;\n                    imageHeight = cellHeight;\n                }\n",
     marker="imageWidth = cellWidth;", desc="getWidgetPreview: drawable sem tamanho")

edit(PV, "                preview = Bitmap.createBitmap(bitmapWidth, bitmapHeight, Config.ARGB_8888);\n"
         "                renderDrawableToBitmap(drawable, preview, 0, 0, bitmapWidth, bitmapHeight);",
     "                bitmapWidth = Math.max(1, bitmapWidth);\n                bitmapHeight = Math.max(1, bitmapHeight);\n"
     "                preview = Bitmap.createBitmap(bitmapWidth, bitmapHeight, Config.ARGB_8888);\n"
     "                renderDrawableToBitmap(drawable, preview, 0, 0, bitmapWidth, bitmapHeight);",
     marker="bitmapHeight = Math.max(1, bitmapHeight);\n                preview", desc="getWidgetPreview: bitmap >= 1x1 (previewImage)")

edit(PV, "            preview = Bitmap.createBitmap(bitmapWidth, bitmapHeight, Config.ARGB_8888);\n"
         "            if (cellHSpan != 1 || cellVSpan != 1) {",
     "            bitmapWidth = Math.max(1, bitmapWidth);\n            bitmapHeight = Math.max(1, bitmapHeight);\n"
     "            preview = Bitmap.createBitmap(bitmapWidth, bitmapHeight, Config.ARGB_8888);\n"
     "            if (cellHSpan != 1 || cellVSpan != 1) {",
     marker="bitmapHeight = Math.max(1, bitmapHeight);\n            preview", desc="getWidgetPreview: bitmap >= 1x1 (gerado)")

# ------------------------------------------------------------------ 7) LauncherModel
edit(SRC / "LauncherModel.java",
     "            // Check if any workspace icons overlap with each other\n",
     "            // Item salvo fora da grade atual: ignora em vez de estourar ArrayIndexOutOfBounds\n"
     "            if (containerIndex < 0 || containerIndex >= occupied.length\n"
     "                    || item.cellX < 0 || item.cellY < 0\n"
     "                    || item.cellX + item.spanX > mCellCountX\n"
     "                    || item.cellY + item.spanY > mCellCountY) {\n"
     "                Log.e(TAG, \"Item fora da grade \" + mCellCountX + \"x\" + mCellCountY + \": \" + item);\n"
     "                return false;\n"
     "            }\n\n"
     "            // Check if any workspace icons overlap with each other\n",
     marker="Item salvo fora da grade atual", desc="checkItemPlacement com limites")

# ------------------------------------------------------------------ resumo
print("== 05: layout de celular ==" + ("  (dry-run)" if DRY else ""))
for c in CHANGED:
    print("  ok  ", c)
if not CHANGED and not WARN:
    print("  nada a fazer (ja aplicado)")
if WARN:
    print("AVISOS:")
    for w in WARN:
        print("  !!  ", w)
