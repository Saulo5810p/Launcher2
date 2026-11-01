#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
11_customization_drawer.py - GAVETA DE PERSONALIZACAO do Honeycomb (etapa 1: layout + estado)

Rode na RAIZ do repo (depois do 08, 09 e 10):  python3 11_customization_drawer.py [--dry-run]
(idempotente; pontos nao encontrados sao listados no final como AVISO, exit 1)

O QUE O HONEYCOMB FAZ (lido do APK com jadx: Launcher, Workspace, CustomizePagedView)
  * Toque longo no espaco vazio (ou botao "+") abre a gaveta: as paginas da workspace ENCOLHEM
    para o topo (escala 0.16, giradas em Y como no Honeycomb), com um brilho azul de fundo, e
    embaixo sobe a bandeja com as abas  Widgets | Atalhos de aplicativo | Papeis de parede | Mais.
  * O toque longo deixa de abrir o seletor de papel de parede.
  * Widgets -> lista de widgets; Atalhos de aplicativo -> aplicativos; Papeis de parede -> apps
    SET_WALLPAPER com preview; Mais -> atalhos CREATE_SHORTCUT. Clicar adiciona na tela atual.

O QUE ESTE SCRIPT FAZ
  1. NOVOS: CustomizeTrayTabHost.java, CustomizePagedView.java (portado para o PagedView do ICS).
  2. Resources do Honeycomb: layouts (customization_drawer*, customize_paged_view_widget),
     customize_bg_gradient.png (brilho azul), widget_divider, ic_home_add_holo_dark, strings
     (en + pt), atributos da CustomizePagedView.
  3. launcher.xml: bandeja, fundo azul e botao "+" (canto superior direito).
  4. Workspace: novo State.CUSTOMIZE (paginas no topo, escala 0.16, rotacao Y, fundo das
     paginas visivel) em changeState().
  5. Launcher: State.CUSTOMIZE / CUSTOMIZE_SPRING_LOADED, abas, abrir/fechar com animacao,
     "+" e toque longo abrem a gaveta, Voltar fecha, lista de apps alimentada pelo modelo.

LIMITES DESTA ETAPA (de proposito, para ser verificavel)
  * Arrastar um item da gaveta: ela some e a workspace entra no modo "spring loaded" do ICS
    (paginas a 75%); ao soltar volta para a gaveta. No Honeycomb voce solta direto nas paginas
    pequenas do topo: isso fica para a etapa 2.
  * O clique adiciona o item sem a animacao de voo do Honeycomb (tambem etapa 2).
  * A gaveta nao e restaurada apos girar a tela (volta para a workspace).
  * As abas "Todos / Meus aplicativos" da gaveta de apps continuam como estao (script 12).
"""
import base64
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


def newfile(path, content, desc=None):
    p = Path(path)
    tag = f"{p.name}: {desc or 'arquivo novo'}"
    if p.exists() and rd(p) == content:
        return
    wr(p, content)
    CHANGED.append(tag if not p.exists() or DRY else tag)


def newbin(path, b64, desc="drawable do Honeycomb"):
    p = Path(path)
    data = base64.b64decode(b64)
    if p.exists() and p.read_bytes() == data:
        return
    if not DRY:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    CHANGED.append(f"{p.parent.name}/{p.name}: {desc}")


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
# 1) Classes novas
# ---------------------------------------------------------------------------------------
TRAY_HOST = r'''/*
 * [11] Host de abas da gaveta de personalizacao (Honeycomb): Widgets / Atalhos de aplicativo /
 * Papeis de parede / Mais. Portado do CustomizeTrayTabHost do Honeycomb.
 * A altura e' proporcional a tela (como o tray do Honeycomb: ~58% em paisagem, ~50% em retrato),
 * assim nao depende de dp fixo (o A35 nao e' um Xoom).
 */
package com.android.launcher2;

import android.animation.Animator;
import android.content.Context;
import android.util.AttributeSet;
import android.view.View;
import android.widget.TabHost;

public class CustomizeTrayTabHost extends TabHost implements LauncherTransitionable {
    private boolean mFirstLayout = true;

    public CustomizeTrayTabHost(Context context) {
        super(context);
    }

    public CustomizeTrayTabHost(Context context, AttributeSet attrs) {
        super(context, attrs);
    }

    /** Altura (px) que o tray ocupa para uma tela de altura {@code parentHeight}. */
    static int trayHeightFor(int parentWidth, int parentHeight) {
        float f = parentWidth > parentHeight ? 0.58f : 0.50f;
        return (int) (parentHeight * f);
    }

    @Override
    protected void onMeasure(int widthMeasureSpec, int heightMeasureSpec) {
        final int h = MeasureSpec.getSize(heightMeasureSpec);
        final int w = MeasureSpec.getSize(widthMeasureSpec);
        super.onMeasure(widthMeasureSpec,
                MeasureSpec.makeMeasureSpec(trayHeightFor(w, h), MeasureSpec.EXACTLY));
    }

    @Override
    public void onLauncherTransitionStart(Launcher l, Animator animation, boolean toWorkspace) {
        if (animation != null) {
            setLayerType(View.LAYER_TYPE_HARDWARE, null);
            if (!mFirstLayout) {
                buildLayer();
            }
        }
    }

    @Override
    public void onLauncherTransitionEnd(Launcher l, Animator animation, boolean toWorkspace) {
        if (animation != null) {
            setLayerType(View.LAYER_TYPE_NONE, null);
        }
    }

    @Override
    protected void onLayout(boolean changed, int l, int t, int r, int b) {
        mFirstLayout = false;
        super.onLayout(changed, l, t, r, b);
    }
}
'''
PAGED_VIEW = r'''/*
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

        mWorkspaceWidgetLayout = new PagedViewCellLayout(context);
        mInflater = LayoutInflater.from(context);
        mMinPageWidth = 0;
        setSoundEffectsEnabled(false);
        setupWorkspaceLayout();
        setDataIsReady();
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
'''
newfile(SRC / "CustomizeTrayTabHost.java", TRAY_HOST)
newfile(SRC / "CustomizePagedView.java", PAGED_VIEW)

# ---------------------------------------------------------------------------------------
# 2) Resources
# ---------------------------------------------------------------------------------------
newfile(RES / "layout/customization_drawer.xml", r'''<?xml version="1.0" encoding="utf-8"?>
<!-- [11] Gaveta de personalizacao do Honeycomb: abas + conteudo (altura definida em
     CustomizeTrayTabHost.onMeasure, proporcional a tela). -->
<com.android.launcher2.CustomizeTrayTabHost
    xmlns:android="http://schemas.android.com/apk/res/android">
    <LinearLayout
        android:orientation="vertical"
        android:layout_width="match_parent"
        android:layout_height="match_parent">
        <TabWidget
            android:id="@android:id/tabs"
            android:layout_gravity="center_horizontal"
            android:layout_width="wrap_content"
            android:layout_height="wrap_content"
            android:background="@drawable/tab_unselected_holo"
            android:tabStripEnabled="false" />
        <FrameLayout
            android:id="@android:id/tabcontent"
            android:layout_width="match_parent"
            android:layout_height="match_parent" />
    </LinearLayout>
</com.android.launcher2.CustomizeTrayTabHost>
''')
newfile(RES / "layout/customization_drawer_tab_contents.xml",
        r'''<?xml version="1.0" encoding="utf-8"?>
<!-- [11] Retrato: mesma grade do Honeycomb (5x3). -->
<com.android.launcher2.CustomizePagedView
    xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:launcher="http://schemas.android.com/apk/res-auto"
    android:layout_width="match_parent"
    android:layout_height="match_parent"
    launcher:cellCountX="5"
    launcher:cellCountY="3"
    launcher:pageLayoutWidthGap="36dp"
    launcher:pageLayoutHeightGap="12dp"
    launcher:pageLayoutPaddingTop="12dp"
    launcher:pageLayoutPaddingBottom="8dp"
    launcher:pageLayoutPaddingLeft="20dp"
    launcher:pageLayoutPaddingRight="20dp"
    launcher:wallpaperCellSpanX="3"
    launcher:wallpaperCellCountX="9"
    launcher:widgetCellCountX="9" />
''')
newfile(RES / "layout-land/customization_drawer_tab_contents.xml",
        r'''<?xml version="1.0" encoding="utf-8"?>
<!-- [11] Paisagem: mesma grade do Honeycomb (8x3). -->
<com.android.launcher2.CustomizePagedView
    xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:launcher="http://schemas.android.com/apk/res-auto"
    android:layout_width="match_parent"
    android:layout_height="match_parent"
    launcher:cellCountX="8"
    launcher:cellCountY="3"
    launcher:pageLayoutWidthGap="32dp"
    launcher:pageLayoutHeightGap="12dp"
    launcher:pageLayoutPaddingTop="12dp"
    launcher:pageLayoutPaddingBottom="8dp"
    launcher:pageLayoutPaddingLeft="20dp"
    launcher:pageLayoutPaddingRight="20dp"
    launcher:wallpaperCellSpanX="3"
    launcher:wallpaperCellCountX="12"
    launcher:widgetCellCountX="14" />
''')
newfile(RES / "layout/customize_paged_view_widget.xml", r'''<?xml version="1.0" encoding="utf-8"?>
<!-- [11] Item de widget/papel de parede da gaveta (igual ao do Honeycomb). -->
<com.android.launcher2.PagedViewWidget
    xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:launcher="http://schemas.android.com/apk/res-auto"
    android:orientation="vertical"
    android:paddingRight="25dp"
    android:paddingBottom="50dp"
    android:layout_width="wrap_content"
    android:layout_height="match_parent"
    android:layout_weight="1.0"
    launcher:blurColor="#ff6b8cf0"
    launcher:outlineColor="#ff8cd2ff">
    <ImageView
        android:id="@+id/widget_preview"
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:scaleType="fitStart"
        android:adjustViewBounds="true"
        android:layout_weight="1.0" />
    <ImageView
        android:id="@+id/customize_divider"
        android:paddingTop="10dp"
        android:paddingBottom="10dp"
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:src="@drawable/widget_divider"
        android:layout_weight="0.0" />
    <TextView
        android:id="@+id/widget_name"
        android:textSize="20sp"
        android:textColor="#ffffffff"
        android:gravity="left"
        android:fadingEdge="horizontal"
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:maxLines="2"
        android:shadowColor="#ff000000"
        android:shadowDx="0.0"
        android:shadowDy="1.0"
        android:shadowRadius="1.0"
        android:layout_weight="0.0" />
    <TextView
        android:id="@+id/widget_dims"
        android:textSize="20sp"
        android:textColor="#ff999999"
        android:gravity="left"
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:shadowColor="#99000000"
        android:shadowDx="0.0"
        android:shadowDy="1.0"
        android:shadowRadius="1.0"
        android:layout_weight="0.0" />
</com.android.launcher2.PagedViewWidget>
''')
newfile(RES / "values/customize_attrs.xml", r'''<?xml version="1.0" encoding="utf-8"?>
<resources>
    <!-- [11] Atributos da gaveta de personalizacao (Honeycomb). -->
    <declare-styleable name="CustomizePagedView">
        <attr name="wallpaperCellSpanX" format="integer" />
        <attr name="wallpaperCellCountX" format="integer" />
        <attr name="widgetCellCountX" format="integer" />
    </declare-styleable>
</resources>
''')
newfile(RES / "values/customize_strings.xml", r'''<?xml version="1.0" encoding="utf-8"?>
<resources>
    <!-- [11] Abas da gaveta de personalizacao (textos do Launcher2 Honeycomb). -->
    <string name="applications_tab_label">App shortcuts</string>
    <string name="wallpapers_tab_label">Wallpapers</string>
    <string name="shortcuts_tab_label">More</string>
</resources>
''')
newfile(RES / "values-pt/customize_strings.xml", r'''<?xml version="1.0" encoding="utf-8"?>
<resources>
    <!-- [11] Abas da gaveta de personalizacao (textos do Launcher2 Honeycomb, pt). -->
    <string name="applications_tab_label">Atalhos de aplicativo</string>
    <string name="wallpapers_tab_label">Papéis de parede</string>
    <string name="shortcuts_tab_label">Mais</string>
</resources>
''')
newbin(RES / "drawable-nodpi/customize_bg_gradient.png", "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", "brilho azul do fundo")
newbin(RES / "drawable-hdpi/widget_divider.png", "iVBORw0KGgoAAAANSUhEUgAAAAIAAAAyCAYAAAB2zAqJAAAAGUlEQVQY02N0c4/fzMDAwMDEAAWjjKHFAAAulAIDMnBjLAAAAABJRU5ErkJggg==", "divisor do item")
newbin(RES / "drawable-mdpi/widget_divider.png", "iVBORw0KGgoAAAANSUhEUgAAAAEAAAAhCAYAAAAYucG/AAAAFElEQVQI12Nwc4/fzMTAwMAwiAkAHBIB4NdaxREAAAAASUVORK5CYII=", "divisor do item")
# (o icone ic_home_add_holo_dark ja existe no ICS e e usado como esta)

# launcher.xml: fundo azul + bandeja + botao "+"
LAUNCHER_XML_ADD = r'''    <!-- [11] gaveta de personalizacao (Honeycomb) -->
    <View
        android:id="@+id/customization_drawer_bg"
        android:layout_width="match_parent"
        android:layout_height="match_parent"
        android:background="@drawable/customize_bg_gradient"
        android:visibility="gone" />

    <include layout="@layout/customization_drawer"
        android:id="@+id/customization_drawer"
        android:layout_width="match_parent"
        android:layout_height="match_parent"
        android:layout_gravity="bottom"
        android:visibility="gone" />

    <ImageView
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

'''
edit(RES / "layout/launcher.xml",
     '    <include layout="@layout/workspace_cling"\n',
     LAUNCHER_XML_ADD + '    <include layout="@layout/workspace_cling"\n',
     marker="customization_drawer_bg", desc="bandeja, fundo azul e botao +")

# ---------------------------------------------------------------------------------------
# 3) Workspace: State.CUSTOMIZE
# ---------------------------------------------------------------------------------------
WS = SRC / "Workspace.java"
edit(WS, "    enum State { NORMAL, SPRING_LOADED, SMALL };",
     "    enum State { NORMAL, SPRING_LOADED, SMALL, CUSTOMIZE };",
     marker="SMALL, CUSTOMIZE }", desc="State.CUSTOMIZE")
edit(WS, "    private static final float WORKSPACE_ROTATION = 12.5f;\n",
     "    private static final float WORKSPACE_ROTATION = 12.5f;\n"
     "    // [11] escala das paginas no topo da gaveta de personalizacao (SHRINK_FACTOR do Honeycomb)\n"
     "    private static final float CUSTOMIZE_SHRINK_FACTOR = 0.16f;\n",
     marker="CUSTOMIZE_SHRINK_FACTOR = 0.16f", desc="constante CUSTOMIZE_SHRINK_FACTOR")
edit(WS, "        return mState == State.SMALL || mState == State.SPRING_LOADED;",
     "        return mState == State.SMALL || mState == State.SPRING_LOADED\n"
     "                || mState == State.CUSTOMIZE;",
     marker="|| mState == State.CUSTOMIZE;", desc="isSmall() inclui CUSTOMIZE")
edit(WS,
     "            finalScaleFactor = mSpringLoadedShrinkFactor - (state == State.SMALL ? 0.1f : 0);\n"
     "            if (oldState == State.NORMAL && state == State.SMALL) {\n",
     "            finalScaleFactor = mSpringLoadedShrinkFactor - (state == State.SMALL ? 0.1f : 0);\n"
     "            if (state == State.CUSTOMIZE) finalScaleFactor = CUSTOMIZE_SHRINK_FACTOR; // [11]\n"
     "            if (oldState == State.NORMAL\n"
     "                    && (state == State.SMALL || state == State.CUSTOMIZE)) {\n",
     marker="finalScaleFactor = CUSTOMIZE_SHRINK_FACTOR; // [11]",
     desc="escala e zoom out do CUSTOMIZE")
edit(WS,
     "        float translationX = 0;\n        float translationY = 0;\n",
     "        if (state == State.CUSTOMIZE) finalBackgroundAlpha = 1.0f; // [11] caixas das paginas\n"
     "        float translationX = 0;\n        float translationY = 0;\n",
     marker="[11] caixas das paginas", desc="fundo das paginas visivel")
edit(WS,
     "            mOldAlphas[i] = cl.getAlpha();\n            mNewAlphas[i] = finalAlphaValue;\n",
     "            // [11] Honeycomb (TOP): pagina no topo, girada em Y (quanto mais longe da atual,\n"
     "            // mais girada) e com a escala X/Y compensada pela rotacao\n"
     "            float pageScaleX = finalScaleFactor;\n"
     "            float pageScaleY = finalScaleFactor;\n"
     "            float pageTranslationY = translationY;\n"
     "            if (state == State.CUSTOMIZE) {\n"
     "                rotation = (mCurrentPage - i) * WORKSPACE_ROTATION;\n"
     "                translationX = 0f;\n"
     "                float cos = (float) Math.cos(Math.toRadians(rotation));\n"
     "                pageScaleX = finalScaleFactor / (cos == 0f ? 1f : cos);\n"
     "                int dist = Math.abs(i - mCurrentPage);\n"
     "                pageScaleY = finalScaleFactor * (dist == 0 ? 0.972f : (dist == 1 ? 1.0f : 1.1f));\n"
     "                float scaledH = finalScaleFactor * cl.getHeight();\n"
     "                float topY = ((getHeight() - mLauncher.getCustomizeTrayHeight()) - scaledH) / 2f;\n"
     "                pageTranslationY = topY - (cl.getHeight() - scaledH) / 2f - cl.getTop();\n"
     "            }\n\n"
     "            mOldAlphas[i] = cl.getAlpha();\n            mNewAlphas[i] = finalAlphaValue;\n",
     marker="float pageTranslationY = translationY;", desc="posicao/rotacao das paginas no topo")
edit(WS, "                mNewTranslationYs[i] = translationY;\n",
     "                mNewTranslationYs[i] = pageTranslationY;\n",
     marker="mNewTranslationYs[i] = pageTranslationY;", desc="animacao: translacao Y")
edit(WS, "                mNewScaleXs[i] = finalScaleFactor;\n                mNewScaleYs[i] = finalScaleFactor;\n",
     "                mNewScaleXs[i] = pageScaleX;\n                mNewScaleYs[i] = pageScaleY;\n",
     marker="mNewScaleXs[i] = pageScaleX;", desc="animacao: escala X/Y")
edit(WS, "                cl.setTranslationY(translationY);\n                cl.setScaleX(finalScaleFactor);\n                cl.setScaleY(finalScaleFactor);\n",
     "                cl.setTranslationY(pageTranslationY);\n                cl.setScaleX(pageScaleX);\n                cl.setScaleY(pageScaleY);\n",
     marker="cl.setTranslationY(pageTranslationY);", desc="sem animacao: translacao e escala")

# ---------------------------------------------------------------------------------------
# 4) Launcher
# ---------------------------------------------------------------------------------------
LA = SRC / "Launcher.java"
LAUNCHER_BLOCK = r'''    // ------------------------------------------------------------------------------------
    // [11] Gaveta de personalizacao (Honeycomb): paginas encolhidas no topo + bandeja com as
    // abas Widgets / Atalhos de aplicativo / Papeis de parede / Mais.
    // Aberta pelo botao "+" e pelo toque longo no espaco vazio.
    // ------------------------------------------------------------------------------------
    private static final String CUSTOMIZE_WIDGETS_TAG = "customize_widgets";
    private static final String CUSTOMIZE_APPLICATIONS_TAG = "customize_applications";
    private static final String CUSTOMIZE_WALLPAPERS_TAG = "customize_wallpapers";
    private static final String CUSTOMIZE_SHORTCUTS_TAG = "customize_shortcuts";

    private CustomizeTrayTabHost mCustomizeTray;
    private CustomizePagedView mCustomizePagedView;
    private View mCustomizeTrayBg;
    private View mCustomizeAddButton;
    private AnimatorSet mCustomizeAnimation;

    private CustomizePagedView.CustomizationType getCustomizeFilterForTabTag(String tag) {
        if (CUSTOMIZE_APPLICATIONS_TAG.equals(tag)) {
            return CustomizePagedView.CustomizationType.ApplicationCustomization;
        } else if (CUSTOMIZE_WALLPAPERS_TAG.equals(tag)) {
            return CustomizePagedView.CustomizationType.WallpaperCustomization;
        } else if (CUSTOMIZE_SHORTCUTS_TAG.equals(tag)) {
            return CustomizePagedView.CustomizationType.ShortcutCustomization;
        }
        return CustomizePagedView.CustomizationType.WidgetCustomization;
    }

    private void addCustomizeTab(android.widget.TabWidget tabWidget,
            android.widget.TabHost.TabContentFactory factory, String tag, int labelRes) {
        TextView tabView = (TextView) getLayoutInflater().inflate(
                R.layout.tab_widget_indicator, tabWidget, false);
        tabView.setText(getString(labelRes));
        tabView.setLayoutParams(new android.widget.LinearLayout.LayoutParams(
                0, ViewGroup.LayoutParams.MATCH_PARENT, 1f));
        mCustomizeTray.addTab(mCustomizeTray.newTabSpec(tag).setIndicator(tabView)
                .setContent(factory));
    }

    private void setupCustomizeTray(DragController dragController) {
        mCustomizeTray = (CustomizeTrayTabHost) mDragLayer.findViewById(R.id.customization_drawer);
        mCustomizeTrayBg = mDragLayer.findViewById(R.id.customization_drawer_bg);
        mCustomizeAddButton = mDragLayer.findViewById(R.id.customize_add_button);
        if (mCustomizeAddButton != null) {
            mCustomizeAddButton.setOnClickListener(new View.OnClickListener() {
                @Override
                public void onClick(View v) {
                    toggleCustomizeDrawer();
                }
            });
        }
        if (mCustomizeTray == null) return;

        mCustomizeTray.setup();
        mCustomizePagedView = (CustomizePagedView) getLayoutInflater().inflate(
                R.layout.customization_drawer_tab_contents, mCustomizeTray, false);
        mCustomizePagedView.setup(this, dragController);

        final android.widget.TabHost.TabContentFactory factory =
                new android.widget.TabHost.TabContentFactory() {
                    @Override
                    public View createTabContent(String tag) {
                        return mCustomizePagedView;
                    }
                };
        android.widget.TabWidget tabWidget = (android.widget.TabWidget)
                mCustomizeTray.findViewById(android.R.id.tabs);
        // a faixa de abas ocupa ~60% da largura (como no Honeycomb)
        ViewGroup.LayoutParams tlp = tabWidget.getLayoutParams();
        tlp.width = (int) (getResources().getDisplayMetrics().widthPixels * 0.6f);
        tabWidget.setLayoutParams(tlp);

        addCustomizeTab(tabWidget, factory, CUSTOMIZE_WIDGETS_TAG, R.string.widgets_tab_label);
        addCustomizeTab(tabWidget, factory, CUSTOMIZE_APPLICATIONS_TAG,
                R.string.applications_tab_label);
        addCustomizeTab(tabWidget, factory, CUSTOMIZE_WALLPAPERS_TAG,
                R.string.wallpapers_tab_label);
        addCustomizeTab(tabWidget, factory, CUSTOMIZE_SHORTCUTS_TAG, R.string.shortcuts_tab_label);

        mCustomizeTray.setOnTabChangedListener(new android.widget.TabHost.OnTabChangeListener() {
            @Override
            public void onTabChanged(String tabId) {
                final CustomizePagedView.CustomizationType newType =
                        getCustomizeFilterForTabTag(tabId);
                if (newType == mCustomizePagedView.getCustomizationFilter()) return;
                final int duration = 150;
                android.animation.ObjectAnimator out = android.animation.ObjectAnimator.ofFloat(
                        mCustomizePagedView, "alpha", mCustomizePagedView.getAlpha(), 0f);
                out.setDuration(duration);
                out.addListener(new android.animation.AnimatorListenerAdapter() {
                    @Override
                    public void onAnimationEnd(android.animation.Animator animation) {
                        mCustomizePagedView.setCustomizationFilter(newType);
                        android.animation.ObjectAnimator in =
                                android.animation.ObjectAnimator.ofFloat(mCustomizePagedView,
                                        "alpha", mCustomizePagedView.getAlpha(), 1f);
                        in.setDuration(duration);
                        in.start();
                    }
                });
                out.start();
            }
        });
        mCustomizePagedView.update();
    }

    int getCustomizeTrayHeight() {
        int w = mDragLayer != null ? mDragLayer.getWidth() : 0;
        int h = mDragLayer != null ? mDragLayer.getHeight() : 0;
        if (w == 0 || h == 0) {
            w = getResources().getDisplayMetrics().widthPixels;
            h = getResources().getDisplayMetrics().heightPixels;
        }
        return CustomizeTrayTabHost.trayHeightFor(w, h);
    }

    public boolean isCustomizeOpen() {
        return mState == State.CUSTOMIZE;
    }

    void toggleCustomizeDrawer() {
        if (mState == State.CUSTOMIZE) {
            showWorkspace(true);
        } else {
            showCustomizeDrawer(true);
        }
    }

    void showCustomizeDrawer(boolean animated) {
        if (mCustomizeTray == null || mState != State.WORKSPACE || isWorkspaceLocked()) return;
        mState = State.CUSTOMIZE;
        mWorkspace.changeState(Workspace.State.CUSTOMIZE, animated);
        mSearchDropTargetBar.hideSearchBar(animated);
        hideHotseat(animated);
        updateWallpaperVisibility(true);
        showCustomizeTray(animated);
    }

    void hideCustomizeDrawer(boolean animated) {
        hideCustomizeTray(animated);
        mSearchDropTargetBar.showSearchBar(animated);
        showHotseat(animated);
    }

    private void showCustomizeTray(boolean animated) {
        if (mCustomizeAnimation != null) mCustomizeAnimation.cancel();
        mCustomizeTray.setVisibility(View.VISIBLE);
        if (mCustomizeTrayBg != null) mCustomizeTrayBg.setVisibility(View.VISIBLE);
        final float h = getCustomizeTrayHeight();
        if (animated) {
            mCustomizeTray.setAlpha(0f);
            mCustomizeTray.setTranslationY(h / 2f);
            if (mCustomizeTrayBg != null) mCustomizeTrayBg.setAlpha(0f);
            mCustomizeAnimation = new AnimatorSet();
            android.animation.ObjectAnimator ty = android.animation.ObjectAnimator.ofFloat(
                    mCustomizeTray, "translationY", h / 2f, 0f);
            android.animation.ObjectAnimator ta = android.animation.ObjectAnimator.ofFloat(
                    mCustomizeTray, "alpha", 0f, 1f);
            if (mCustomizeTrayBg != null) {
                android.animation.ObjectAnimator ba = android.animation.ObjectAnimator.ofFloat(
                        mCustomizeTrayBg, "alpha", 0f, 1f);
                mCustomizeAnimation.playTogether(ty, ta, ba);
            } else {
                mCustomizeAnimation.playTogether(ty, ta);
            }
            mCustomizeAnimation.setDuration(450);
            mCustomizeAnimation.setInterpolator(new DecelerateInterpolator(1.8f));
            mCustomizeAnimation.start();
        } else {
            mCustomizeTray.setAlpha(1f);
            mCustomizeTray.setTranslationY(0f);
            if (mCustomizeTrayBg != null) mCustomizeTrayBg.setAlpha(1f);
        }
    }

    private void hideCustomizeTray(boolean animated) {
        if (mCustomizeTray == null) return;
        if (mCustomizeAnimation != null) mCustomizeAnimation.cancel();
        final float h = getCustomizeTrayHeight();
        if (animated && mCustomizeTray.getVisibility() == View.VISIBLE) {
            mCustomizeAnimation = new AnimatorSet();
            android.animation.ObjectAnimator ty = android.animation.ObjectAnimator.ofFloat(
                    mCustomizeTray, "translationY", mCustomizeTray.getTranslationY(), h / 2f);
            android.animation.ObjectAnimator ta = android.animation.ObjectAnimator.ofFloat(
                    mCustomizeTray, "alpha", mCustomizeTray.getAlpha(), 0f);
            if (mCustomizeTrayBg != null) {
                android.animation.ObjectAnimator ba = android.animation.ObjectAnimator.ofFloat(
                        mCustomizeTrayBg, "alpha", mCustomizeTrayBg.getAlpha(), 0f);
                mCustomizeAnimation.playTogether(ty, ta, ba);
            } else {
                mCustomizeAnimation.playTogether(ty, ta);
            }
            mCustomizeAnimation.setDuration(350);
            mCustomizeAnimation.setInterpolator(new AccelerateInterpolator(1.2f));
            mCustomizeAnimation.addListener(new android.animation.AnimatorListenerAdapter() {
                private boolean mCancelled = false;

                @Override
                public void onAnimationCancel(android.animation.Animator animation) {
                    mCancelled = true;
                }

                @Override
                public void onAnimationEnd(android.animation.Animator animation) {
                    if (mCancelled) return;
                    mCustomizeTray.setVisibility(View.GONE);
                    if (mCustomizeTrayBg != null) mCustomizeTrayBg.setVisibility(View.GONE);
                }
            });
            mCustomizeAnimation.start();
        } else {
            mCustomizeTray.setVisibility(View.GONE);
            if (mCustomizeTrayBg != null) mCustomizeTrayBg.setVisibility(View.GONE);
        }
    }

    /** Arrasto iniciado na gaveta: ela some e a workspace fica em modo spring loaded. */
    void enterCustomizeSpringLoadedDragMode() {
        if (mState == State.CUSTOMIZE) {
            mWorkspace.changeState(Workspace.State.SPRING_LOADED);
            hideCustomizeTray(true);
            showHotseat(true);
            mState = State.CUSTOMIZE_SPRING_LOADED;
        }
    }

    void exitCustomizeSpringLoadedDragMode() {
        if (mState == State.CUSTOMIZE_SPRING_LOADED) {
            mWorkspace.changeState(Workspace.State.CUSTOMIZE);
            showCustomizeTray(true);
            hideHotseat(true);
            mState = State.CUSTOMIZE;
        }
    }

    void exitCustomizeSpringLoadedDragModeDelayed(boolean successfulDrop) {
        if (mState != State.CUSTOMIZE_SPRING_LOADED) return;
        mHandler.postDelayed(new Runnable() {
            @Override
            public void run() {
                exitCustomizeSpringLoadedDragMode();
            }
        }, successfulDrop ? EXIT_SPRINGLOADED_MODE_LONG_TIMEOUT
                : EXIT_SPRINGLOADED_MODE_SHORT_TIMEOUT);
    }

'''
edit(LA, "    private enum State { WORKSPACE, APPS_CUSTOMIZE, APPS_CUSTOMIZE_SPRING_LOADED };",
     "    private enum State { WORKSPACE, APPS_CUSTOMIZE, APPS_CUSTOMIZE_SPRING_LOADED,\n"
     "            CUSTOMIZE, CUSTOMIZE_SPRING_LOADED };",
     marker="CUSTOMIZE, CUSTOMIZE_SPRING_LOADED }", desc="State.CUSTOMIZE / CUSTOMIZE_SPRING_LOADED")
edit(LA, "        mAppsCustomizeContent.setup(this, dragController);\n",
     "        mAppsCustomizeContent.setup(this, dragController);\n"
     "        setupCustomizeTray(dragController); // [11]\n",
     marker="setupCustomizeTray(dragController); // [11]", desc="monta a bandeja")
edit(LA, "    void showWorkspace(boolean animated) {\n",
     LAUNCHER_BLOCK + "    void showWorkspace(boolean animated) {\n",
     marker="[11] Gaveta de personalizacao (Honeycomb): paginas", desc="codigo da gaveta")
edit(LA,
     "        if (mState == State.APPS_CUSTOMIZE) {\n            closeAllApps(animated);\n        }\n\n        mWorkspace.showDockDivider(!animated);",
     "        if (mState == State.APPS_CUSTOMIZE) {\n            closeAllApps(animated);\n        }\n"
     "        if (mState == State.CUSTOMIZE || mState == State.CUSTOMIZE_SPRING_LOADED) { // [11]\n"
     "            hideCustomizeDrawer(animated);\n        }\n\n        mWorkspace.showDockDivider(!animated);",
     marker="hideCustomizeDrawer(animated);\n        }\n\n        mWorkspace.showDockDivider", desc="showWorkspace fecha a gaveta")
edit(LA, "    public void onBackPressed() {\n        if (mState == State.APPS_CUSTOMIZE) {\n",
     "    public void onBackPressed() {\n        if (mState == State.APPS_CUSTOMIZE || mState == State.CUSTOMIZE) { // [11]\n",
     marker="mState == State.CUSTOMIZE) { // [11]", desc="Voltar fecha a gaveta")
edit(LA, "    private void addItems() {\n        showWorkspace(true);\n        showAddDialog();\n    }",
     "    private void addItems() {\n        toggleCustomizeDrawer(); // [11] gaveta de personalizacao no lugar do dialogo\n    }",
     marker="toggleCustomizeDrawer(); // [11]", desc="addItems abre a gaveta")
edit(LA,
     "                mWorkspace.performHapticFeedback(HapticFeedbackConstants.LONG_PRESS,\n"
     "                        HapticFeedbackConstants.FLAG_IGNORE_VIEW_SETTING);\n"
     "                startWallpaper();\n",
     "                mWorkspace.performHapticFeedback(HapticFeedbackConstants.LONG_PRESS,\n"
     "                        HapticFeedbackConstants.FLAG_IGNORE_VIEW_SETTING);\n"
     "                showCustomizeDrawer(true); // [11] toque longo abre a gaveta (nao o papel de parede)\n",
     marker="showCustomizeDrawer(true); // [11]", desc="toque longo abre a gaveta")
edit(LA, "                    mAppsCustomizeContent.setApps(apps);\n                }\n",
     "                    mAppsCustomizeContent.setApps(apps);\n                }\n"
     "                if (mCustomizePagedView != null) mCustomizePagedView.setApps(apps); // [11]\n",
     marker="mCustomizePagedView.setApps(apps); // [11]", desc="apps da gaveta (carga)")
edit(LA, "            mAppsCustomizeContent.addApps(apps);\n        }\n",
     "            mAppsCustomizeContent.addApps(apps);\n        }\n"
     "        if (mCustomizePagedView != null) mCustomizePagedView.addApps(apps); // [11]\n",
     marker="mCustomizePagedView.addApps(apps); // [11]", desc="apps da gaveta (instalado)")
edit(LA, "            mAppsCustomizeContent.updateApps(apps);\n        }\n",
     "            mAppsCustomizeContent.updateApps(apps);\n        }\n"
     "        if (mCustomizePagedView != null) mCustomizePagedView.updateApps(apps); // [11]\n",
     marker="mCustomizePagedView.updateApps(apps); // [11]", desc="apps da gaveta (atualizado)")
edit(LA, "            mAppsCustomizeContent.removeApps(apps);\n        }\n",
     "            mAppsCustomizeContent.removeApps(apps);\n        }\n"
     "        if (mCustomizePagedView != null) mCustomizePagedView.removeApps(apps); // [11]\n",
     marker="mCustomizePagedView.removeApps(apps); // [11]", desc="apps da gaveta (removido)")
edit(LA, "    public void bindPackagesUpdated() {\n        if (mAppsCustomizeContent != null) {\n            mAppsCustomizeContent.onPackagesUpdated();\n        }\n",
     "    public void bindPackagesUpdated() {\n        if (mAppsCustomizeContent != null) {\n            mAppsCustomizeContent.onPackagesUpdated();\n        }\n"
     "        if (mCustomizePagedView != null) mCustomizePagedView.update(); // [11]\n",
     marker="mCustomizePagedView.update(); // [11]", desc="widgets/atalhos da gaveta (pacotes)")

# ---------------------------------------------------------------------------------------
print("== 11: gaveta de personalizacao (etapa 1)" + ("  (dry-run)" if DRY else "") + " ==")
for c in CHANGED:
    print("  ok  ", c)
if not CHANGED and not WARN:
    print("  nada a fazer (ja aplicado)")
if WARN:
    print("AVISOS:")
    for w in WARN:
        print("  !!  ", w)
    sys.exit(1)
