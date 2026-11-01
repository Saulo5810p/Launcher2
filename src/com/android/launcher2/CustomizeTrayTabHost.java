/*
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
