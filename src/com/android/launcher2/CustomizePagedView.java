/*
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
