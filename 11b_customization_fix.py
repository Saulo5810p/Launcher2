#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
11b_customization_fix.py - correcoes da gaveta de personalizacao (script 11)

Rode na RAIZ do repo, depois do 11:  python3 11b_customization_fix.py [--dry-run]
(idempotente; pontos nao encontrados viram AVISO no final, exit 1)

CORRIGE
  1. CRASH ao clicar num item da gaveta (NullPointerException em Workspace.onDropExternal):
     o clique chama onDropExternal sem DragObject (d == null) e o codigo lia d.dragView.
     - icone/aplicativo: so anima o voo se houver DragObject.
     - widget e atalho (PendingAddItemInfo): sem arrasto, entra direto no primeiro espaco livre
       (antes tambem quebrava em touchXY[0]).
  2. Botao "+" movido para a barra de busca (search_bar.xml), no canto direito, com divisor e o
     botao de todos os apps ao lado, como no button_bar do Honeycomb. Some junto com a barra
     quando a gaveta abre.
  3. Tocar numa pagina encolhida abre ESSA pagina (como o Honeycomb: onWorkspaceClick ->
     showWorkspace(animated, layout)). No ICS tocar na vizinha so rolava.
  4. Paginas sobrepostas: afastamento extra proporcional a distancia da pagina atual.
  5. Abas: uma/duas linhas, sem caixa alta, faixa em toda a largura (retrato) ou 76% (paisagem).
  6. Grade espremida: a gaveta mede o espaco real e escolhe colunas, linhas e tamanho da celula
     (a celula fixa de 96dp nao cabia nos ~384dp de altura do A35). Item de widget com textos
     menores para o preview aparecer.
"""
import sys
from pathlib import Path

DRY = "--dry-run" in sys.argv
SRC = Path("src/com/android/launcher2")
RES = Path("res")
CHANGED, WARN = [], []


def rd(p):
    return Path(p).read_text(encoding="utf-8")


def wr(p, t):
    if not DRY:
        Path(p).parent.mkdir(parents=True, exist_ok=True)
        Path(p).write_text(t, encoding="utf-8")


def newfile(path, content, desc):
    p = Path(path)
    if p.exists() and rd(p) == content:
        return
    wr(p, content)
    CHANGED.append(f"{p.name}: {desc}")


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
# Workspace
# ---------------------------------------------------------------------------------------
WS = SRC / "Workspace.java"

# 1) crash: DragObject nulo no clique
edit(WS, "            if (d.dragView != null) {\n                // We wrap the animation call",
     "            if (d != null && d.dragView != null) {\n                // We wrap the animation call",
     marker="if (d != null && d.dragView != null) {", desc="crash: d.dragView com d nulo (icone)")
edit(WS,
     "            boolean findNearestVacantCell = true;\n"
     "            if (pendingInfo.itemType == LauncherSettings.Favorites.ITEM_TYPE_SHORTCUT) {\n",
     "            if (d == null || touchXY == null) {\n"
     "                // [11b] clique na gaveta (sem arrasto): primeiro espaco livre, sem animacao de voo\n"
     "                cellLayout.findCellForSpan(mTargetCell, spanX, spanY);\n"
     "                switch (pendingInfo.itemType) {\n"
     "                case LauncherSettings.Favorites.ITEM_TYPE_APPWIDGET:\n"
     "                    mLauncher.addAppWidgetFromDrop((PendingAddWidgetInfo) pendingInfo,\n"
     "                            container, screen, mTargetCell, null);\n"
     "                    break;\n"
     "                case LauncherSettings.Favorites.ITEM_TYPE_SHORTCUT:\n"
     "                    mLauncher.processShortcutFromDrop(pendingInfo.componentName,\n"
     "                            container, screen, mTargetCell, null);\n"
     "                    break;\n"
     "                default:\n"
     "                    throw new IllegalStateException(\"Unknown item type: \" +\n"
     "                            pendingInfo.itemType);\n"
     "                }\n"
     "                cellLayout.onDragExit();\n"
     "                return;\n"
     "            }\n\n"
     "            boolean findNearestVacantCell = true;\n"
     "            if (pendingInfo.itemType == LauncherSettings.Favorites.ITEM_TYPE_SHORTCUT) {\n",
     marker="[11b] clique na gaveta (sem arrasto)", desc="crash: clique em widget/atalho sem DragObject")

# 3) tocar na pagina abre ESSA pagina
edit(WS,
     "        return LauncherApplication.isScreenLarge() && hitsPage(current - 1, x, y);",
     "        return mState != State.CUSTOMIZE && LauncherApplication.isScreenLarge()\n"
     "                && hitsPage(current - 1, x, y); // [11b] na gaveta o toque abre a pagina",
     marker="hitsPage(current - 1, x, y); // [11b]", desc="toque na pagina anterior")
edit(WS,
     "        return LauncherApplication.isScreenLarge() && hitsPage(current + 1, x, y);",
     "        return mState != State.CUSTOMIZE && LauncherApplication.isScreenLarge()\n"
     "                && hitsPage(current + 1, x, y); // [11b] na gaveta o toque abre a pagina",
     marker="hitsPage(current + 1, x, y); // [11b]", desc="toque na pagina seguinte")
edit(WS, "        cl.setOnInterceptTouchListener(this);\n",
     "        cl.setOnInterceptTouchListener(this);\n"
     "        cl.setOnClickListener(new OnClickListener() { // [11b] toque na pagina encolhida\n"
     "            @Override\n"
     "            public void onClick(View v) {\n"
     "                if (mState == State.CUSTOMIZE) {\n"
     "                    mLauncher.onCustomizePageClicked((CellLayout) v);\n"
     "                }\n"
     "            }\n"
     "        });\n"
     "        cl.setClickable(false); // [11b] so fica clicavel com a gaveta aberta (changeState)\n",
     marker="[11b] toque na pagina encolhida", desc="clique na pagina encolhida")
edit(WS, "        float translationX = 0;\n        float translationY = 0;\n",
     "        for (int c = 0; c < getChildCount(); c++) { // [11b] paginas clicaveis so na gaveta\n"
     "            getChildAt(c).setClickable(state == State.CUSTOMIZE);\n"
     "        }\n"
     "        float translationX = 0;\n        float translationY = 0;\n",
     marker="setClickable(state == State.CUSTOMIZE)", desc="paginas clicaveis so na gaveta")

# 4) paginas sobrepostas
edit(WS, "                translationX = 0f;\n                float cos = (float) Math.cos(Math.toRadians(rotation));\n",
     "                // [11b] afastamento extra: as paginas giradas se sobrepunham\n"
     "                translationX = (i - mCurrentPage) * 0.16f * finalScaleFactor * cl.getWidth();\n"
     "                float cos = (float) Math.cos(Math.toRadians(rotation));\n",
     marker="[11b] afastamento extra", desc="afastamento entre paginas")

# ---------------------------------------------------------------------------------------
# PagedViewCellLayout: tamanho de celula ajustavel
# ---------------------------------------------------------------------------------------
edit(SRC / "PagedViewCellLayout.java",
     "    public int getCellWidth() {\n        return mCellWidth;\n    }\n",
     "    /** [11b] tamanho de celula ajustavel (gaveta de personalizacao). */\n"
     "    void setCellSize(int width, int height) {\n"
     "        if (width == mCellWidth && height == mCellHeight) return;\n"
     "        mOriginalCellWidth = mCellWidth = width;\n"
     "        mOriginalCellHeight = mCellHeight = height;\n"
     "        mChildren.setCellDimensions(width, height);\n"
     "        mHolographicChildren.setCellDimensions(width, height);\n"
     "        requestLayout();\n"
     "    }\n\n"
     "    public int getCellWidth() {\n        return mCellWidth;\n    }\n",
     marker="void setCellSize(int width, int height)", desc="setCellSize()")

# ---------------------------------------------------------------------------------------
# Launcher
# ---------------------------------------------------------------------------------------
LA = SRC / "Launcher.java"
edit(LA, "    void exitCustomizeSpringLoadedDragModeDelayed(boolean successfulDrop) {\n",
     "    /** [11b] Tocar numa pagina encolhida abre essa pagina (Honeycomb: onWorkspaceClick). */\n"
     "    void onCustomizePageClicked(CellLayout layout) {\n"
     "        if (mState != State.CUSTOMIZE) return;\n"
     "        int index = mWorkspace.indexOfChild(layout);\n"
     "        if (index >= 0) {\n"
     "            mWorkspace.setCurrentPage(index);\n"
     "        }\n"
     "        showWorkspace(true);\n"
     "    }\n\n"
     "    void exitCustomizeSpringLoadedDragModeDelayed(boolean successfulDrop) {\n",
     marker="void onCustomizePageClicked(CellLayout layout)", desc="onCustomizePageClicked()")
edit(LA,
     "        tabView.setText(getString(labelRes));\n",
     "        tabView.setText(getString(labelRes));\n"
     "        // [11b] sem caixa alta/negrito e com ate 2 linhas (o texto quebrava letra por letra)\n"
     "        final float density = getResources().getDisplayMetrics().density;\n"
     "        tabView.setAllCaps(false);\n"
     "        tabView.setTypeface(android.graphics.Typeface.DEFAULT);\n"
     "        tabView.setTextSize(android.util.TypedValue.COMPLEX_UNIT_SP, 15);\n"
     "        tabView.setMaxLines(2);\n"
     "        tabView.setEllipsize(android.text.TextUtils.TruncateAt.END);\n"
     "        tabView.setPadding((int) (6 * density), (int) (8 * density),\n"
     "                (int) (6 * density), (int) (10 * density));\n",
     marker="[11b] sem caixa alta/negrito", desc="texto das abas")
edit(LA,
     "        ViewGroup.LayoutParams tlp = tabWidget.getLayoutParams();\n"
     "        tlp.width = (int) (getResources().getDisplayMetrics().widthPixels * 0.6f);\n"
     "        tabWidget.setLayoutParams(tlp);\n",
     "        // [11b] retrato: toda a largura; paisagem: faixa central (12% de folga de cada lado)\n"
     "        android.widget.LinearLayout.LayoutParams tlp =\n"
     "                (android.widget.LinearLayout.LayoutParams) tabWidget.getLayoutParams();\n"
     "        android.util.DisplayMetrics dm = getResources().getDisplayMetrics();\n"
     "        int tabMargin = dm.widthPixels > dm.heightPixels ? (int) (dm.widthPixels * 0.12f) : 0;\n"
     "        tlp.width = ViewGroup.LayoutParams.MATCH_PARENT;\n"
     "        tlp.leftMargin = tabMargin;\n"
     "        tlp.rightMargin = tabMargin;\n"
     "        tabWidget.setLayoutParams(tlp);\n",
     marker="[11b] retrato: toda a largura", desc="largura da faixa de abas")

# ---------------------------------------------------------------------------------------
# Layouts: botao "+" na barra de busca (Honeycomb: button_bar)
# ---------------------------------------------------------------------------------------
edit(RES / "layout/launcher.xml",
     '''    <ImageView
        android:id="@+id/customize_add_button"
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:layout_gravity="top|right"
        android:padding="16dp"
        android:src="@drawable/ic_home_add_holo_dark"
        android:contentDescription="@string/widgets_tab_label"
        android:background="?android:attr/selectableItemBackground"
        android:clickable="true"
        android:focusable="true" />

''',
     "    <!-- [11b] o botao + agora fica em search_bar.xml, ao lado do botao de todos os apps -->\n\n",
     marker="[11b] o botao + agora fica", desc="remove o botao + solto")
SB = RES / "layout/search_bar.xml"
edit(SB,
     '        android:layout_alignParentRight="true"\n'
     '        android:layout_alignParentTop="true"\n'
     '        android:layout_toLeftOf="@+id/all_apps_divider"\n',
     '        android:layout_alignParentTop="true"\n'
     '        android:layout_toLeftOf="@+id/customize_divider"\n',
     marker='android:layout_toLeftOf="@+id/customize_divider"', desc="all apps ao lado do divisor")
edit(SB, "</RelativeLayout>",
     '''
    <!-- [11b] divisor + botao "+" (gaveta de personalizacao), canto direito como no Honeycomb -->
    <ImageView
        style="@style/SearchButtonDivider"
        android:id="@+id/customize_divider"
        android:layout_toLeftOf="@+id/customize_add_button"
        android:src="@drawable/divider_launcher_holo"
        android:focusable="false"
        android:clickable="false" />

    <com.android.launcher2.HolographicImageView
        style="@style/SearchButton"
        android:id="@+id/customize_add_button"
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:layout_alignParentRight="true"
        android:layout_alignParentTop="true"
        android:src="@drawable/ic_home_add_holo_dark"
        android:focusable="true"
        android:clickable="true"
        android:contentDescription="@string/widgets_tab_label" />
</RelativeLayout>''',
     marker='android:id="@+id/customize_add_button"', desc='botao + e divisor')

# ---------------------------------------------------------------------------------------
# Gaveta: grade adaptativa + item de widget
# ---------------------------------------------------------------------------------------
newfile(SRC / "CustomizePagedView.java", r'''/*
 * [11] Conteudo da gaveta de personalizacao do Honeycomb: Widgets / Atalhos de aplicativo
 * (aplicativos) / Papeis de parede / Mais (atalhos CREATE_SHORTCUT).
 * Portado do CustomizePagedView do Honeycomb para as APIs do PagedView do ICS.
 *
 * ETAPA 1: clique adiciona o item na tela atual; segurar e arrastar usa o mesmo arrasto do ICS
 * (a gaveta some e a workspace entra em modo "spring loaded"; ao soltar, volta para a gaveta).
 */
package com.android.launcher2;

import android.appwidget.AppWidgetManager;
import android.appwidget.AppWidgetProviderInfo;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import android.content.res.Resources;
import android.content.res.TypedArray;
import android.content.res.XmlResourceParser;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Rect;
import android.graphics.RectF;
import android.graphics.drawable.Drawable;
import android.util.AttributeSet;
import android.util.Log;
import android.util.Xml;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;

import com.android.launcher.R;

import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.List;

public class CustomizePagedView extends PagedViewWithDraggableItems
        implements View.OnClickListener, DragSource {
    private static final String TAG = "CustomizePagedView";
    private static final int sMaxWidgetCellHSpan = 4;
    private static final int sMinWidgetCellHSpan = 2;
    private static final float sScaleFactor = 0.75f;

    public enum CustomizationType {
        WidgetCustomization,
        ShortcutCustomization,
        WallpaperCustomization,
        ApplicationCustomization
    }

    private Launcher mLauncher;
    private DragController mDragController;
    private PackageManager mPackageManager;
    private final LayoutInflater mInflater;
    private final Canvas mCanvas = new Canvas();
    private final HolographicOutlineHelper mHoloHelper = new HolographicOutlineHelper();

    private CustomizationType mCustomizationType = CustomizationType.WidgetCustomization;

    private List<ApplicationInfo> mApps = new ArrayList<ApplicationInfo>();
    private List<AppWidgetProviderInfo> mWidgetList = new ArrayList<AppWidgetProviderInfo>();
    private List<ResolveInfo> mShortcutList = new ArrayList<ResolveInfo>();
    private List<ResolveInfo> mWallpaperList = new ArrayList<ResolveInfo>();
    private final ArrayList<ArrayList<AppWidgetProviderInfo>> mWidgetPages =
            new ArrayList<ArrayList<AppWidgetProviderInfo>>();

    private final PagedViewCellLayout mWorkspaceWidgetLayout;
    private int mWallpaperCellHSpan;
    private int mMaxWallpaperCellHSpan;
    private int mMaxWidgetsCellHSpan;
    private int mMaxWidgetWidth;
    private int mMinPageWidth;
    // [11b] grade adaptativa: o numero de colunas/linhas e o tamanho da celula dependem do
    // espaco real da bandeja (o A35 tem ~384dp de altura, bem menos que um Xoom)
    private int mMaxCellCountX;
    private int mMaxCellCountY;
    private int mCellW = -1;
    private int mCellH = -1;
    private int mGridW = -1;
    private int mGridH = -1;

    /** Pagina de widgets/papeis de parede: LinearLayout que tambem e' uma Page do PagedView. */
    static class TrayPage extends LinearLayout implements Page {
        public TrayPage(Context context) {
            super(context);
        }

        @Override
        public int getPageChildCount() {
            return getChildCount();
        }

        @Override
        public View getChildOnPageAt(int i) {
            return getChildAt(i);
        }

        @Override
        public void removeAllViewsOnPage() {
            removeAllViews();
        }

        @Override
        public void removeViewOnPageAt(int i) {
            removeViewAt(i);
        }

        @Override
        public int indexOfChildOnPage(View v) {
            return indexOfChild(v);
        }
    }

    public CustomizePagedView(Context context) {
        this(context, null, 0);
    }

    public CustomizePagedView(Context context, AttributeSet attrs) {
        this(context, attrs, 0);
    }

    public CustomizePagedView(Context context, AttributeSet attrs, int defStyle) {
        super(context, attrs, defStyle);
        TypedArray a = context.obtainStyledAttributes(attrs, R.styleable.CustomizePagedView,
                defStyle, 0);
        mWallpaperCellHSpan = a.getInt(R.styleable.CustomizePagedView_wallpaperCellSpanX, 3);
        mMaxWallpaperCellHSpan = a.getInt(R.styleable.CustomizePagedView_wallpaperCellCountX, 9);
        mMaxWidgetsCellHSpan = a.getInt(R.styleable.CustomizePagedView_widgetCellCountX, 9);
        a.recycle();

        a = context.obtainStyledAttributes(attrs, R.styleable.PagedView, defStyle, 0);
        mCellCountX = a.getInt(R.styleable.PagedView_cellCountX, 7);
        mCellCountY = a.getInt(R.styleable.PagedView_cellCountY, 4);
        a.recycle();
        mMaxCellCountX = mCellCountX;
        mMaxCellCountY = mCellCountY;

        mWorkspaceWidgetLayout = new PagedViewCellLayout(context);
        mInflater = LayoutInflater.from(context);
        mMinPageWidth = 0;
        setSoundEffectsEnabled(false);
        setupWorkspaceLayout();
        setDataIsReady();
    }

    @Override
    protected void onMeasure(int widthMeasureSpec, int heightMeasureSpec) {
        final int w = MeasureSpec.getSize(widthMeasureSpec);
        final int h = MeasureSpec.getSize(heightMeasureSpec);
        if (w > 0 && h > 0 && (w != mGridW || h != mGridH)) {
            mGridW = w;
            mGridH = h;
            updateGrid(w, h);
        }
        super.onMeasure(widthMeasureSpec, heightMeasureSpec);
    }

    /** Calcula colunas, linhas e tamanho de celula que cabem no espaco da bandeja. */
    private void updateGrid(int w, int h) {
        final float d = getResources().getDisplayMetrics().density;
        final int gapW = Math.max(0, mPageLayoutWidthGap);
        final int gapH = Math.max(0, mPageLayoutHeightGap);
        final int availH = h - mPageLayoutPaddingTop - mPageLayoutPaddingBottom;
        final int availW = w - mPageLayoutPaddingLeft - mPageLayoutPaddingRight;
        final int maxCellH = (int) (96 * d);
        final int minCellH = (int) (72 * d);
        int rows = Math.max(1, Math.min(mMaxCellCountY, (availH + gapH) / (minCellH + gapH)));
        int cellH = Math.max(1, Math.min(maxCellH, (availH - gapH * (rows - 1)) / rows));
        int cellW = cellH * 80 / 96;
        int cols = Math.max(1, Math.min(mMaxCellCountX, (availW + gapW) / (cellW + gapW)));
        if (cols != mCellCountX || rows != mCellCountY || cellW != mCellW || cellH != mCellH) {
            mCellCountX = cols;
            mCellCountY = rows;
            mCellW = cellW;
            mCellH = cellH;
            post(new Runnable() {
                @Override
                public void run() {
                    invalidatePageData();
                }
            });
        }
    }

    @Override
    protected void init() {
        super.init();
        mCenterPagesVertically = false;
    }

    public void setup(Launcher launcher, DragController dragController) {
        mLauncher = launcher;
        mDragController = dragController;
        mPackageManager = getContext().getPackageManager();
    }

    /* ---------------------------------------------------------------------------------- */
    /* Dados                                                                              */
    /* ---------------------------------------------------------------------------------- */

    public void setApps(ArrayList<ApplicationInfo> list) {
        mApps = new ArrayList<ApplicationInfo>(list);
        Collections.sort(mApps, LauncherModel.APP_NAME_COMPARATOR);
        invalidatePageData();
    }

    private void addAppsWithoutInvalidate(ArrayList<ApplicationInfo> list) {
        for (int i = 0; i < list.size(); i++) {
            ApplicationInfo info = list.get(i);
            int index = Collections.binarySearch(mApps, info, LauncherModel.APP_NAME_COMPARATOR);
            if (index < 0) {
                mApps.add(-(index + 1), info);
            }
        }
    }

    public void addApps(ArrayList<ApplicationInfo> list) {
        addAppsWithoutInvalidate(list);
        invalidatePageData();
    }

    private void removeAppsWithoutInvalidate(ArrayList<ApplicationInfo> list) {
        for (int i = 0; i < list.size(); i++) {
            ApplicationInfo info = list.get(i);
            int removeIndex = findAppByComponent(mApps, info);
            if (removeIndex > -1) {
                mApps.remove(removeIndex);
            }
        }
    }

    public void removeApps(ArrayList<ApplicationInfo> list) {
        removeAppsWithoutInvalidate(list);
        invalidatePageData();
    }

    public void updateApps(ArrayList<ApplicationInfo> list) {
        removeAppsWithoutInvalidate(list);
        addAppsWithoutInvalidate(list);
        invalidatePageData();
    }

    private int findAppByComponent(List<ApplicationInfo> list, ApplicationInfo item) {
        ComponentName removeComponent = item.intent.getComponent();
        for (int i = 0; i < list.size(); i++) {
            ApplicationInfo info = list.get(i);
            if (info.intent.getComponent().equals(removeComponent)) {
                return i;
            }
        }
        return -1;
    }

    /** Recarrega widgets, atalhos e papeis de parede instalados. */
    public void update() {
        if (mLauncher == null) return;
        mWidgetList = new ArrayList<AppWidgetProviderInfo>(
                AppWidgetManager.getInstance(mLauncher).getInstalledProviders());
        Collections.sort(mWidgetList, new Comparator<AppWidgetProviderInfo>() {
            @Override
            public int compare(AppWidgetProviderInfo a, AppWidgetProviderInfo b) {
                String la = a.label == null ? "" : a.label;
                String lb = b.label == null ? "" : b.label;
                return la.compareTo(lb);
            }
        });
        Comparator<ResolveInfo> byLabel = new Comparator<ResolveInfo>() {
            @Override
            public int compare(ResolveInfo a, ResolveInfo b) {
                return a.loadLabel(mPackageManager).toString()
                        .compareTo(b.loadLabel(mPackageManager).toString());
            }
        };
        mShortcutList = new ArrayList<ResolveInfo>(mPackageManager.queryIntentActivities(
                new Intent(Intent.ACTION_CREATE_SHORTCUT), 0));
        Collections.sort(mShortcutList, byLabel);
        mWallpaperList = new ArrayList<ResolveInfo>(mPackageManager.queryIntentActivities(
                new Intent(Intent.ACTION_SET_WALLPAPER), PackageManager.GET_META_DATA));
        Collections.sort(mWallpaperList, byLabel);
        invalidatePageData();
    }

    public void setCustomizationFilter(CustomizationType filterType) {
        cancelDragging();
        mCustomizationType = filterType;
        if (getChildCount() > 0) {
            setCurrentPage(0);
            updateCurrentPageScroll();
        }
        invalidatePageData(0);
        endChoiceMode();
    }

    public CustomizationType getCustomizationFilter() {
        return mCustomizationType;
    }

    /* ---------------------------------------------------------------------------------- */
    /* Clique: adiciona o item na tela atual (ou aplica o papel de parede)                */
    /* ---------------------------------------------------------------------------------- */

    @Override
    public void onClick(final View v) {
        if (mLauncher == null || !v.isInTouchMode() || mNextPage != INVALID_PAGE) return;
        if (!mLauncher.isCustomizeOpen()) return;

        if (mCustomizationType == CustomizationType.WallpaperCustomization) {
            animateClickFeedback(v, new Runnable() {
                @Override
                public void run() {
                    ResolveInfo info = (ResolveInfo) v.getTag();
                    Intent intent = new Intent(Intent.ACTION_SET_WALLPAPER);
                    intent.setComponent(new ComponentName(info.activityInfo.packageName,
                            info.activityInfo.name));
                    mLauncher.processWallpaper(intent);
                }
            });
            return;
        }

        final ItemInfo itemInfo = (ItemInfo) v.getTag();
        if (itemInfo == null) return;
        final Workspace w = mLauncher.getWorkspace();
        final CellLayout cl = (CellLayout) w.getChildAt(mLauncher.getCurrentWorkspaceScreen());
        animateClickFeedback(v, new Runnable() {
            @Override
            public void run() {
                prepareSpans(itemInfo);
                cl.calculateSpans(itemInfo);
                if (cl.findCellForSpan(null, itemInfo.spanX, itemInfo.spanY)) {
                    ItemInfo toAdd = itemInfo;
                    if (itemInfo instanceof ApplicationInfo) {
                        toAdd = new ApplicationInfo((ApplicationInfo) itemInfo);
                    }
                    mLauncher.addExternalItemToScreen(toAdd, cl);
                } else {
                    mLauncher.showOutOfSpaceMessage();
                }
            }
        });
    }

    private void prepareSpans(ItemInfo info) {
        if (info instanceof PendingAddWidgetInfo) {
            int[] span = mLauncher.getSpanForWidget((PendingAddWidgetInfo) info, null);
            info.spanX = span[0];
            info.spanY = span[1];
        } else {
            info.spanX = 1;
            info.spanY = 1;
        }
    }

    /* ---------------------------------------------------------------------------------- */
    /* Arrasto                                                                            */
    /* ---------------------------------------------------------------------------------- */

    @Override
    protected void determineDraggingStart(android.view.MotionEvent ev) {
        // arrastar "puxando para baixo" fica desligado (so toque longo)
    }

    @Override
    protected boolean beginDragging(View v) {
        if (mLauncher == null || !v.isInTouchMode() || !super.beginDragging(v)) return false;
        if (isChoiceMode(CHOICE_MODE_SINGLE)) endChoiceMode();

        // a gaveta some e a workspace entra em modo spring loaded (antes do startDrag)
        mLauncher.enterCustomizeSpringLoadedDragMode();

        Workspace workspace = mLauncher.getWorkspace();
        boolean result = false;
        switch (mCustomizationType) {
            case WidgetCustomization:
                if (v instanceof PagedViewWidget) {
                    ImageView image = (ImageView) v.findViewById(R.id.widget_preview);
                    PendingAddWidgetInfo info = (PendingAddWidgetInfo) v.getTag();
                    RectF scaleRect = new RectF(0f, 0f, 1f, 1f);
                    image.getImageMatrix().mapRect(scaleRect);
                    Drawable preview = image.getDrawable();
                    int w = (int) (preview.getIntrinsicWidth() * scaleRect.right);
                    int h = (int) (preview.getIntrinsicHeight() * scaleRect.bottom);
                    Bitmap b = Bitmap.createBitmap(Math.max(1, w), Math.max(1, h),
                            Bitmap.Config.ARGB_8888);
                    renderDrawableToBitmap(preview, b, 0, 0, w, h, scaleRect.right,
                            scaleRect.bottom);
                    int[] span = mLauncher.getSpanForWidget(info, null);
                    info.spanX = span[0];
                    info.spanY = span[1];
                    mLauncher.lockScreenOrientationOnLargeUI();
                    workspace.onDragStartedWithItemSpans(info.spanX, info.spanY, b);
                    mDragController.startDrag(image, b, this, info,
                            DragController.DRAG_ACTION_COPY, null);
                    b.recycle();
                    result = true;
                }
                break;
            case ApplicationCustomization:
                if (v instanceof PagedViewIcon) {
                    workspace.onDragStartedWithItem(v);
                    workspace.beginDragShared(v, this);
                    result = true;
                }
                break;
            case ShortcutCustomization:
                if (v instanceof PagedViewIcon) {
                    PendingAddItemInfo info = (PendingAddItemInfo) v.getTag();
                    info.spanX = 1;
                    info.spanY = 1;
                    Drawable icon = ((TextView) v).getCompoundDrawables()[1];
                    int s = Math.max(1, icon.getIntrinsicWidth());
                    Bitmap b = Bitmap.createBitmap(s, Math.max(1, icon.getIntrinsicHeight()),
                            Bitmap.Config.ARGB_8888);
                    renderDrawableToBitmap(icon, b, 0, 0, b.getWidth(), b.getHeight(), 1f, 1f);
                    mLauncher.lockScreenOrientationOnLargeUI();
                    workspace.onDragStartedWithItemSpans(1, 1, b);
                    mDragController.startDrag(v, b, this, info,
                            DragController.DRAG_ACTION_COPY, null);
                    b.recycle();
                    result = true;
                }
                break;
            default:
                break;
        }
        if (!result) {
            mLauncher.exitCustomizeSpringLoadedDragMode();
        }
        return result;
    }

    @Override
    public void onDropCompleted(View target, DropTarget.DragObject d, boolean success) {
        mLauncher.getWorkspace().onDragStopped(success);
        mLauncher.unlockScreenOrientationOnLargeUI();
        // soltou na workspace: ela ja tratou o drop; volta para a gaveta (apos um instante)
        mLauncher.exitCustomizeSpringLoadedDragModeDelayed(success);
        if (!success && target instanceof Workspace) {
            Workspace workspace = (Workspace) target;
            CellLayout layout = (CellLayout) workspace.getChildAt(
                    mLauncher.getCurrentWorkspaceScreen());
            ItemInfo itemInfo = (ItemInfo) d.dragInfo;
            if (layout != null && itemInfo != null) {
                layout.calculateSpans(itemInfo);
                if (!layout.findCellForSpan(null, itemInfo.spanX, itemInfo.spanY)) {
                    mLauncher.showOutOfSpaceMessage();
                }
            }
        }
    }

    /* ---------------------------------------------------------------------------------- */
    /* Previews                                                                           */
    /* ---------------------------------------------------------------------------------- */

    private void renderDrawableToBitmap(Drawable d, Bitmap bitmap, int x, int y, int w, int h,
            float scaleX, float scaleY) {
        if (bitmap != null) {
            mCanvas.setBitmap(bitmap);
        }
        mCanvas.save();
        mCanvas.scale(scaleX, scaleY);
        Rect oldBounds = d.copyBounds();
        d.setBounds(x, y, x + w, y + h);
        d.draw(mCanvas);
        d.setBounds(oldBounds);
        mCanvas.restore();
        if (bitmap != null) {
            mCanvas.setBitmap(null);
        }
    }

    private void drawIconOnPreview(Bitmap bitmap, Drawable icon, int minDim) {
        if (icon == null) return;
        int iconSize = minDim / 2;
        int offset = iconSize / 4;
        renderDrawableToBitmap(icon, bitmap, offset, offset, iconSize, iconSize, 1f, 1f);
    }

    private Drawable getDefaultPreviewBackground() {
        return getResources().getDrawable(R.drawable.default_widget_preview_holo);
    }

    private FastBitmapDrawable getWidgetPreview(AppWidgetProviderInfo info) {
        final String packageName = info.provider.getPackageName();
        Drawable drawable = null;
        if (info.previewImage != 0) {
            drawable = mPackageManager.getDrawable(packageName, info.previewImage, null);
            if (drawable == null) {
                Log.w(TAG, "Can't load preview 0x" + Integer.toHexString(info.previewImage)
                        + " for provider: " + info.provider);
            }
        }
        int minDim = mWorkspaceWidgetLayout.estimateCellWidth(1);
        int maxDim = mWorkspaceWidgetLayout.estimateCellWidth(3);
        Bitmap bitmap;
        if (drawable == null) {
            int width = (int) (Math.max(minDim, Math.min(maxDim, info.minWidth)) * sScaleFactor);
            int height = (int) (Math.max(minDim, Math.min(maxDim, info.minHeight)) * sScaleFactor);
            bitmap = Bitmap.createBitmap(Math.max(1, width), Math.max(1, height),
                    Bitmap.Config.ARGB_8888);
            renderDrawableToBitmap(getDefaultPreviewBackground(), bitmap, 0, 0, width, height,
                    1f, 1f);
            Drawable icon = null;
            try {
                if (info.icon > 0) {
                    icon = mPackageManager.getDrawable(packageName, info.icon, null);
                }
                if (icon == null) {
                    icon = getResources().getDrawable(R.drawable.ic_launcher_application);
                }
                drawIconOnPreview(bitmap, icon, minDim);
            } catch (Resources.NotFoundException e) {
                // sem icone
            }
        } else {
            float iw = drawable.getIntrinsicWidth();
            float ih = drawable.getIntrinsicHeight();
            float aspect = iw / ih;
            int scaledW = (int) (Math.max(minDim, Math.min(maxDim, iw)) * sScaleFactor);
            int scaledH = (int) (Math.max(minDim, Math.min(maxDim, ih)) * sScaleFactor);
            int width, height;
            if (aspect >= 1f) {
                width = scaledW;
                height = (int) ((scaledW / iw) * ih);
            } else {
                height = scaledH;
                width = (int) ((scaledH / ih) * iw);
            }
            bitmap = Bitmap.createBitmap(Math.max(1, width), Math.max(1, height),
                    Bitmap.Config.ARGB_8888);
            renderDrawableToBitmap(drawable, bitmap, 0, 0, width, height, 1f, 1f);
        }
        FastBitmapDrawable d = new FastBitmapDrawable(bitmap);
        d.setBounds(0, 0, d.getIntrinsicWidth(), d.getIntrinsicHeight());
        return d;
    }

    /** Le o drawable declarado em android.wallpaper.preview (se o app de papel de parede tiver). */
    private Drawable parseWallpaperPreviewXml(ResolveInfo info) {
        XmlResourceParser parser = null;
        try {
            parser = info.activityInfo.loadXmlMetaData(mPackageManager,
                    "android.wallpaper.preview");
            if (parser == null) return null;
            int type;
            while ((type = parser.next()) != XmlResourceParser.END_DOCUMENT
                    && type != XmlResourceParser.START_TAG) {
                // avanca ate a primeira tag
            }
            if (!"wallpaper-preview".equals(parser.getName())) return null;
            int resId = parser.getAttributeResourceValue(
                    "http://schemas.android.com/apk/res/android", "staticWallpaperPreview", 0);
            if (resId == 0) return null;
            Resources res = mPackageManager.getResourcesForApplication(
                    info.activityInfo.applicationInfo);
            return res.getDrawable(resId);
        } catch (Exception e) {
            Log.w(TAG, "wallpaper-preview invalido em " + info.activityInfo.name, e);
            return null;
        } finally {
            if (parser != null) parser.close();
        }
    }

    private FastBitmapDrawable getWallpaperPreview(ResolveInfo info) {
        int minDim = mWorkspaceWidgetLayout.estimateCellWidth(1);
        int dim = mWorkspaceWidgetLayout.estimateCellWidth(mWallpaperCellHSpan);
        int size = Math.max(1, (int) (dim * sScaleFactor));
        Bitmap bitmap = Bitmap.createBitmap(size, size, Bitmap.Config.ARGB_8888);
        Drawable custom = parseWallpaperPreviewXml(info);
        if (custom != null) {
            renderDrawableToBitmap(custom, bitmap, 0, 0, size, size, 1f, 1f);
        } else {
            renderDrawableToBitmap(getDefaultPreviewBackground(), bitmap, 0, 0, size, size,
                    1f, 1f);
            try {
                IconCache iconCache = ((LauncherApplication) mLauncher.getApplication())
                        .getIconCache();
                Drawable icon = new FastBitmapDrawable(Utilities.createIconBitmap(
                        iconCache.getFullResIcon(info, mPackageManager), getContext()));
                drawIconOnPreview(bitmap, icon, minDim);
            } catch (Resources.NotFoundException e) {
                // sem icone
            }
        }
        FastBitmapDrawable d = new FastBitmapDrawable(bitmap);
        d.setBounds(0, 0, d.getIntrinsicWidth(), d.getIntrinsicHeight());
        return d;
    }

    /* ---------------------------------------------------------------------------------- */
    /* Paginas                                                                            */
    /* ---------------------------------------------------------------------------------- */

    private void setupWorkspaceLayout() {
        mWorkspaceWidgetLayout.setCellCount(mCellCountX, mCellCountY);
        mWorkspaceWidgetLayout.setPadding(20, 10, 20, 0);
        mMaxWidgetWidth = mWorkspaceWidgetLayout.estimateCellWidth(4);
    }

    private void setupPage(PagedViewCellLayout layout) {
        layout.setCellCount(mCellCountX, mCellCountY);
        if (mCellW > 0 && mCellH > 0) layout.setCellSize(mCellW, mCellH);
        layout.setPadding(mPageLayoutPaddingLeft, mPageLayoutPaddingTop,
                mPageLayoutPaddingRight, mPageLayoutPaddingBottom);
        layout.setGap(mPageLayoutWidthGap, mPageLayoutHeightGap);
    }

    private TrayPage newTrayPage() {
        TrayPage layout = new TrayPage(getContext());
        layout.setGravity(android.view.Gravity.CENTER_HORIZONTAL);
        layout.setPadding(mPageLayoutPaddingLeft, mPageLayoutPaddingTop,
                mPageLayoutPaddingRight, mPageLayoutPaddingBottom);
        return layout;
    }

    private int relayoutWidgets() {
        mWidgetPages.clear();
        if (mWidgetList.isEmpty()) return 0;
        ArrayList<AppWidgetProviderInfo> newPage = new ArrayList<AppWidgetProviderInfo>();
        mWidgetPages.add(newPage);
        int numCellsInRow = 0;
        for (int i = 0; i < mWidgetList.size(); i++) {
            AppWidgetProviderInfo info = mWidgetList.get(i);
            int cellSpanX = Math.max(sMinWidgetCellHSpan, Math.min(sMaxWidgetCellHSpan,
                    mWorkspaceWidgetLayout.estimateCellHSpan(info.minWidth)));
            if (numCellsInRow + cellSpanX > mMaxWidgetsCellHSpan) {
                numCellsInRow = 0;
                newPage = new ArrayList<AppWidgetProviderInfo>();
                mWidgetPages.add(newPage);
            }
            newPage.add(info);
            numCellsInRow += cellSpanX;
        }
        return mWidgetPages.size();
    }

    private void syncWidgetPages() {
        removeAllViews();
        int numPages = relayoutWidgets();
        for (int i = 0; i < numPages; i++) {
            addView(newTrayPage(), new LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.MATCH_PARENT));
        }
    }

    private void syncWidgetPageItems(int page) {
        TrayPage layout = (TrayPage) getChildAt(page);
        ArrayList<AppWidgetProviderInfo> list = mWidgetPages.get(page);
        layout.removeAllViews();
        for (int i = 0; i < list.size(); i++) {
            AppWidgetProviderInfo info = list.get(i);
            PendingAddWidgetInfo createItemInfo = new PendingAddWidgetInfo(info, null, null);
            int[] cellSpans = CellLayout.rectToCell(getResources(), info.minWidth,
                    info.minHeight, null);
            PagedViewWidget l = (PagedViewWidget) mInflater.inflate(
                    R.layout.customize_paged_view_widget, layout, false);
            l.applyFromAppWidgetProviderInfo(info, mMaxWidgetWidth, cellSpans, mHoloHelper);
            l.applyPreview(getWidgetPreview(info), 0, true);
            l.setTag(createItemInfo);
            l.setOnClickListener(this);
            l.setOnTouchListener(this);
            l.setOnLongClickListener(this);
            layout.addView(l);
        }
    }

    private void syncWallpaperPages() {
        removeAllViews();
        int perPage = Math.max(1, mMaxWallpaperCellHSpan / mWallpaperCellHSpan);
        int numPages = (mWallpaperList.size() + perPage - 1) / perPage;
        for (int i = 0; i < numPages; i++) {
            addView(newTrayPage(), new LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.MATCH_PARENT));
        }
    }

    private void syncWallpaperPageItems(int page) {
        TrayPage layout = (TrayPage) getChildAt(page);
        layout.removeAllViews();
        int perPage = Math.max(1, mMaxWallpaperCellHSpan / mWallpaperCellHSpan);
        int start = page * perPage;
        int end = Math.min(mWallpaperList.size(), start + perPage);
        for (int i = start; i < end; i++) {
            ResolveInfo info = mWallpaperList.get(i);
            PagedViewWidget l = (PagedViewWidget) mInflater.inflate(
                    R.layout.customize_paged_view_widget, layout, false);
            l.applyFromResolveInfo(mPackageManager, info, mHoloHelper);
            View dims = l.findViewById(R.id.widget_dims);
            if (dims != null) dims.setVisibility(View.GONE);
            l.applyPreview(getWallpaperPreview(info), 0, true);
            l.setTag(info);
            l.setOnClickListener(this);
            layout.addView(l);
        }
    }

    private void syncCellPages(int count) {
        removeAllViews();
        int perPage = Math.max(1, mCellCountX * mCellCountY);
        int numPages = (count + perPage - 1) / perPage;
        for (int i = 0; i < numPages; i++) {
            PagedViewCellLayout layout = new PagedViewCellLayout(getContext());
            setupPage(layout);
            addView(layout);
        }
    }

    private void syncAppPageItems(int page) {
        int numCells = mCellCountX * mCellCountY;
        int start = page * numCells;
        int end = Math.min(start + numCells, mApps.size());
        PagedViewCellLayout layout = (PagedViewCellLayout) getChildAt(page);
        layout.removeAllViewsOnPage();
        for (int i = start; i < end; i++) {
            ApplicationInfo info = mApps.get(i);
            PagedViewIcon icon = (PagedViewIcon) mInflater.inflate(
                    R.layout.apps_customize_application, layout, false);
            icon.applyFromApplicationInfo(info, true, mHoloHelper);
            icon.setOnClickListener(this);
            icon.setOnTouchListener(this);
            icon.setOnLongClickListener(this);
            int index = i - start;
            setupPage(layout);
            layout.addViewToCellLayout(icon, -1, i, new PagedViewCellLayout.LayoutParams(
                    index % mCellCountX, index / mCellCountX, 1, 1));
        }
    }

    private void syncShortcutPageItems(int page) {
        int numCells = mCellCountX * mCellCountY;
        int start = page * numCells;
        int end = Math.min(start + numCells, mShortcutList.size());
        PagedViewCellLayout layout = (PagedViewCellLayout) getChildAt(page);
        layout.removeAllViewsOnPage();
        IconCache iconCache = ((LauncherApplication) mLauncher.getApplication()).getIconCache();
        for (int i = start; i < end; i++) {
            ResolveInfo info = mShortcutList.get(i);
            PendingAddItemInfo createItemInfo = new PendingAddItemInfo();
            createItemInfo.itemType = LauncherSettings.Favorites.ITEM_TYPE_SHORTCUT;
            createItemInfo.componentName = new ComponentName(info.activityInfo.packageName,
                    info.activityInfo.name);
            PagedViewIcon icon = (PagedViewIcon) mInflater.inflate(
                    R.layout.apps_customize_application, layout, false);
            Bitmap iconBitmap = Utilities.createIconBitmap(iconCache.getFullResIcon(info, mPackageManager),
                    getContext());
            icon.setCompoundDrawablesWithIntrinsicBounds(null,
                    new FastBitmapDrawable(iconBitmap), null, null);
            icon.setText(info.loadLabel(mPackageManager));
            icon.setTag(createItemInfo);
            icon.setOnClickListener(this);
            icon.setOnTouchListener(this);
            icon.setOnLongClickListener(this);
            int index = i - start;
            setupPage(layout);
            layout.addViewToCellLayout(icon, -1, i, new PagedViewCellLayout.LayoutParams(
                    index % mCellCountX, index / mCellCountX, 1, 1));
        }
    }

    @Override
    public void syncPages() {
        boolean enforceMinimumPagedWidths = false;
        boolean centerCellLayouts = false;
        switch (mCustomizationType) {
            case WidgetCustomization:
                syncWidgetPages();
                enforceMinimumPagedWidths = true;
                break;
            case ApplicationCustomization:
                syncCellPages(mApps.size());
                break;
            case ShortcutCustomization:
                syncCellPages(mShortcutList.size());
                centerCellLayouts = true;
                break;
            case WallpaperCustomization:
                syncWallpaperPages();
                enforceMinimumPagedWidths = true;
                break;
            default:
                removeAllViews();
                setCurrentPage(0);
                break;
        }
        final int childCount = getChildCount();
        if (centerCellLayouts) {
            for (int i = 0; i < childCount; i++) {
                ((PagedViewCellLayout) getChildAt(i)).enableCenteredContent(childCount == 1);
            }
        }
        if (enforceMinimumPagedWidths) {
            setMinimumWidthOverride(childCount > 1 ? mMinPageWidth : 0);
        }
        requestLayout();
        post(new Runnable() {
            @Override
            public void run() {
                setCurrentPage(Math.max(0, Math.min(childCount - 1, getCurrentPage())));
                forceUpdateAdjacentPagesAlpha();
            }
        });
    }

    @Override
    public void syncPageItems(int page, boolean immediate) {
        if (page >= getChildCount()) return;
        switch (mCustomizationType) {
            case WidgetCustomization:
                syncWidgetPageItems(page);
                break;
            case ApplicationCustomization:
                syncAppPageItems(page);
                break;
            case ShortcutCustomization:
                syncShortcutPageItems(page);
                break;
            case WallpaperCustomization:
                syncWallpaperPageItems(page);
                break;
            default:
                break;
        }
    }

    @Override
    protected int getAssociatedLowerPageBound(int page) {
        return 0;
    }

    @Override
    protected int getAssociatedUpperPageBound(int page) {
        return getChildCount();
    }

    /** Largura minima de pagina (px) usada nas abas de widgets e papeis de parede. */
    void setMinPageWidth(int px) {
        mMinPageWidth = px;
    }
}
''',
        "grade adaptativa (colunas/linhas/celula pelo espaco real)")
newfile(RES / "layout/customize_paged_view_widget.xml", r'''<?xml version="1.0" encoding="utf-8"?>
<!-- [11] Item de widget/papel de parede da gaveta (Honeycomb). [11b] textos e margens
     reduzidos: o preview ocupa o espaco que sobra (antes ficava com altura zero). -->
<com.android.launcher2.PagedViewWidget
    xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:launcher="http://schemas.android.com/apk/res-auto"
    android:orientation="vertical"
    android:paddingRight="16dp"
    android:paddingBottom="6dp"
    android:layout_width="wrap_content"
    android:layout_height="match_parent"
    launcher:blurColor="#ff6b8cf0"
    launcher:outlineColor="#ff8cd2ff">
    <ImageView
        android:id="@+id/widget_preview"
        android:layout_width="wrap_content"
        android:layout_height="0dp"
        android:layout_weight="1.0"
        android:scaleType="fitStart"
        android:adjustViewBounds="true" />
    <ImageView
        android:id="@+id/customize_divider"
        android:paddingTop="4dp"
        android:paddingBottom="4dp"
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:src="@drawable/widget_divider" />
    <TextView
        android:id="@+id/widget_name"
        android:textSize="13sp"
        android:textColor="#ffffffff"
        android:gravity="left"
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:maxWidth="160dp"
        android:maxLines="1"
        android:ellipsize="end"
        android:shadowColor="#ff000000"
        android:shadowDx="0.0"
        android:shadowDy="1.0"
        android:shadowRadius="1.0" />
    <TextView
        android:id="@+id/widget_dims"
        android:textSize="12sp"
        android:textColor="#ff999999"
        android:gravity="left"
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:shadowColor="#99000000"
        android:shadowDx="0.0"
        android:shadowDy="1.0"
        android:shadowRadius="1.0" />
</com.android.launcher2.PagedViewWidget>
''',
        "item de widget com textos menores")

print("== 11b: correcoes da gaveta de personalizacao" + ("  (dry-run)" if DRY else "") + " ==")
for c in CHANGED:
    print("  ok  ", c)
if not CHANGED and not WARN:
    print("  nada a fazer (ja aplicado)")
if WARN:
    print("AVISOS:")
    for w in WARN:
        print("  !!  ", w)
    sys.exit(1)
