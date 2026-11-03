/***************************************************************************
 *             __________               __   ___.
 *   Open      \______   \ ____   ____ |  | _\_ |__   _______  ___
 *   Source     |       _//  _ \_/ ___\|  |/ /| __ \ /  _ \  \/  /
 *   Jukebox    |    |   (  <_> )  \___|    < | \_\ (  <_> > <  <
 *   Firmware   |____|_  /\____/ \___  >__|_ \|___  /\____/__/\_ \
 *                     \/            \/     \/    \/            \/
 *
 * Copyright (C) Daniel Stenberg (2002)
 * Copyright (C) William Wilgus (2026)
 *
 * This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License
 * as published by the Free Software Foundation; either version 2
 * of the License, or (at your option) any later version.
 *
 * This software is distributed on an "AS IS" basis, WITHOUT WARRANTY OF ANY
 * KIND, either express or implied.
 *
 ****************************************************************************/
#include "stdarg.h"
#include "string.h"
#include "rbunicode.h"
#include "stdio.h"
#include "kernel.h"
#include "screen_access.h"
#include "lang.h"
#include "settings.h"
#include "talk.h"
#include "splash.h"
#include "viewport.h"
#include "strptokspn_r.h"
#include "scrollbar.h"
#include "font.h"
#ifndef BOOTLOADER
#include "misc.h" /* get_current_activity */
#endif

static long progress_next_tick, talked_tick;

#define MAXLINES  (LCD_HEIGHT/6)


#ifndef BOOTLOADER
#if MEMORYSIZE > 8
    #define MAXBUFFER MAX(1024, (LCD_WIDTH/SYSFONT_WIDTH) * MAXLINES + 1)
#else
    #define MAXBUFFER MAX(512, (LCD_WIDTH/SYSFONT_WIDTH) * MAXLINES + 1)
#endif
#else
    #define MAXBUFFER (512)
#endif

#if defined(PODTHINGS_OS) && defined(HAVE_LCD_COLOR) && !defined(BOOTLOADER)
#define PODTHINGS_MODERN_SPLASH
#define RECT_SPACING 12
#define SPLASH_TOP_DETAIL 12
#else
#define RECT_SPACING 3
#define SPLASH_TOP_DETAIL 0
#endif
#define SPLASH_MEMORY_INTERVAL (HZ)

#ifdef PODTHINGS_MODERN_SPLASH
/* Static firmware names only; never a pointer to a temporary message. */
static const char *reboot_target;
void splash_set_reboot_target(const char *target) { reboot_target=target; }
const char *splash_reboot_target(void) { return reboot_target; }

static unsigned popup_foreground(void)
{
    unsigned bg=global_settings.bg_color, fg=global_settings.fg_color;
    if (bg==fg)
        fg=RGB_UNPACK_RED(bg)+RGB_UNPACK_GREEN(bg)+RGB_UNPACK_BLUE(bg)>382 ?
           LCD_RGBPACK(16,16,24) : LCD_RGBPACK(248,248,255);
    return fg;
}

static unsigned popup_blend(unsigned a, unsigned b, unsigned weight)
{
    return LCD_RGBPACK((RGB_UNPACK_RED(a)*(12-weight)+RGB_UNPACK_RED(b)*weight)/12,
                      (RGB_UNPACK_GREEN(a)*(12-weight)+RGB_UNPACK_GREEN(b)*weight)/12,
                      (RGB_UNPACK_BLUE(a)*(12-weight)+RGB_UNPACK_BLUE(b)*weight)/12);
}

static void popup_round_fill(struct screen *s, int x, int y, int w, int h,
                             int radius, unsigned color)
{
    if (w<=0 || h<=0) return;
    radius=MIN(radius,MIN(w/2,h/2));
    s->set_foreground(color);
    for (int row=0;row<h;row++)
    {
        int dy=row<radius ? radius-row : row>=h-radius ? row-(h-radius-1) : 0;
        int span=radius;
        if (dy) {
            span=0;
            while (span<radius && (span+1)*(span+1)+dy*dy<=radius*radius) ++span;
        }
        int inset=radius-span;
        s->fillrect(x+inset,y+row,w-inset*2,1);
    }
}

static void popup_card(struct screen *s, struct viewport *vp)
{
    unsigned bg=global_settings.bg_color, fg=popup_foreground();
    vp->drawmode=DRMODE_FG;
    popup_round_fill(s,0,0,vp->width,vp->height,12,popup_blend(bg,fg,3));
    popup_round_fill(s,1,1,vp->width-2,vp->height-2,11,popup_blend(bg,fg,1));
    popup_round_fill(s,(vp->width-36)/2,8,36,3,1,global_settings.lss_color);
    s->set_foreground(fg);
}

void splash_draw_card(struct screen *screen, struct viewport *vp)
{
    popup_card(screen,vp);
}

static void popup_progress(struct screen *s, struct viewport *vp,int current,int total)
{
    unsigned flags=vp->flags;
    vp->flags&=~VP_FLAG_ALIGN_CENTER;
    const int pad=RECT_SPACING;
    int size=s->getcharheight(), text_width=0, text_height;
    char percent[12];
    unsigned fg=popup_foreground(), bg=global_settings.bg_color;
    if (total>0)
    {
        int value=(int)((int64_t)MAX(0,MIN(current,total))*100/total);
        snprintf(percent,sizeof(percent),"%d%%",value);
        s->getstringsize((const unsigned char *)percent,&text_width,&text_height);
        s->set_foreground(fg);
        s->putsxy(vp->width-pad-text_width,vp->height-pad-size,
                  (const unsigned char *)percent);
    }
    int w=vp->width-pad*2-(text_width?text_width+10:0);
    int y=vp->height-pad-size/2-3;
    popup_round_fill(s,pad,y,w,6,3,popup_blend(bg,fg,2));
    int fill=total>0 ? (int)((int64_t)MAX(0,MIN(current,total))*w/total) : MAX(12,w/4);
    int x=pad;
    if (total<=0 && w>fill)
    {
        unsigned travel=w-fill;
        unsigned phase=((uint32_t)current_tick/2)%(travel*2);
        x+=phase>travel ? travel*2-phase : phase;
    }
    if (fill>0) popup_round_fill(s,x,y,fill,6,MIN(3,fill/2),global_settings.lss_color);
    vp->flags=flags;
}
#endif

/* splash_internal does the actual drawing of the splash box and text
 * each call to splash remembers the max size and will not shrink the splash box
 * until it is reset by an activity change or \f at the beginning of a string
 *
 * splash supports several escape sequences ("\n\t\f\r\v\b")
 * '\n' (new line) indicates the end of a line of text and starts a new one
 *  ("\n\n" will end a line and create a blank line)
 *  '\n' as the first character of the text will create a blank line
 *
 * '\t' (tab) starts a new line and adds several spaces to the beginning of the
 *  new line it also left/right justifies the splash text box
 *  (RTL languages will right justify)
 * '\t' as the last character of the text will left/right justify
 *  without adding any tabs to the text output
 *
 * '\f' (form feed) as the first character of the text will reset the text box
 *  width and height
 *
 * Others:
 * '\f', \r', '\v' '\b' will be treated as a breaking space character
 *  they will not be displayed as output and multiple sequences will be
 *  treated as a single character
 *  eg. "\b\v\f\r" will break the line but only once and will not show as a space
 *  where as "\n\n" will break a line and add a blank line
 *  "\t\t" would break a line and add a total of 4 spaces to the next line
*/
static bool splash_internal(struct screen * screen, const char *fmt, va_list ap,
                            struct viewport *vp, int addl_lines)
{
    static const char matchstr[] = "\r\n\f\v\t\b";
    static int max_width[NB_SCREENS] = {0};
    static int max_height[NB_SCREENS] = {0};
#ifndef BOOTLOADER
    static char splash_buf[MAXBUFFER] = {0};
    static enum current_activity last_act = ACTIVITY_UNKNOWN;
    enum current_activity act = get_current_activity();

    if (last_act != act) /* changed activities reset width / height */
    {
        FOR_NB_SCREENS(i)
        {
            max_width[i] = 0;
            max_height[i] = 0;
        }
        last_act = act;
    }
#else /*def BOOTLOADER*/
    char splash_buf[MAXBUFFER] = {0}; /* on the stack for the bootloader */
#endif

    struct splash_lines {
        const char *str;
        uint16_t x;
        uint16_t len;
    } lines[MAXLINES];
    memset(lines, 0, sizeof(lines));

    char *buf = splash_buf;
    const char *next, *store;

    bool has_tabs = false;
    int line = 0;
    int x = 0, w = 0;
    int y;
    int space_w, chr_h;
    int width = vp->width - RECT_SPACING*2;
    int height = vp->height;
#ifdef PODTHINGS_MODERN_SPLASH
    height-=SPLASH_TOP_DETAIL+RECT_SPACING*2;
    width=MIN(width,272);
#endif

    /* prevent screen artifacts by keeping the max width / height seen */
    int maxw = max_width[screen->screen_type];
    int maxh = max_height[screen->screen_type];
    int fontnum = vp->font;

    size_t next_len;

    font_getstringsize(" ", &space_w, &chr_h, fontnum);
    y = (addl_lines * chr_h);

    int res = vsnprintf(splash_buf, sizeof(splash_buf), fmt, ap);
    va_end(ap);

    if (res <= 0 || width < space_w || height < chr_h)
    {
#ifdef SIMULATOR
        if (res <= 0)
            printf("ERROR: %s %d\n", __func__, res);
        else
            printf("WARNING: %s vp too small\n", __func__);
#endif
        return false; /* nothing to display */
    }

    const char *lastbreak = splash_buf;
    if (*lastbreak == '\f') /* only as first character - Reset splash box size */
    {
        maxw = 0;
        maxh = 0;
    }

    while(true) /* break splash string into display lines, doing proper word wrap */
    {
#ifndef BOOTLOADER
        while (*lastbreak != '\0') /* handle escape chars*/
        {
            switch (*lastbreak) /* all chars in matchstr */
            {
                case '\t': /*fallthrough*/
                    has_tabs = true; /* left justify (right justify for RTL)*/
                case '\n':
                {
                    if (lines[line].len > 0 || *lastbreak != '\t')
                    {
                        x += w;
                        if (x > maxw)
                            maxw = x;

                        x = 0;
                        y += chr_h;
                        if (y >= height || line >= MAXLINES-1)
                        {
                            break;  /* out of lines */
                        }
                        line++;
                    }
                    /* /t as last char left justifies only */
                    if (lastbreak[0] == '\t' && lastbreak[1] != '\0')
                    {
                        /* add offset for tab */
                        lines[line].x += space_w * 2;
                        x += space_w * 2;
                    }
                    break;
                }
                case '\b': /*fallthrough*/
                case '\f': /*fallthrough*/
                case '\v': /*fallthrough*/
                case '\r':
                    break; /* acts the same as a space character */
                default: /* No valid break chars */
                    lastbreak = " "; /* exit */
                    break;
            }
            lastbreak++;
        }
#endif
        if (lines[line].len > 0)
        {
            x += w;
            if (x > maxw)
                maxw = x;
            x = 0;
            y += chr_h;
            if (y >= height || line >= MAXLINES-1)
            {
                if (y > maxh)
                    maxh = y;
                break;  /* out of lines */
            }
            line++;
        }

        next = strptokspn_r(buf, matchstr, &next_len, &store);

        if (!next)
        {
            x += w;
            if (x > maxw)
                maxw = x;
            if (y > maxh)
                maxh = y;
            break;
        }
        buf = NULL; /* uses store for continuation */

        lines[line].str = next;
        lines[line].len = next_len;

        w = font_getstringnsize(next, next_len, NULL, NULL, fontnum);
        if (w > width)
        {
            const char *nxp, *nx = next;
            int nw, newlen;
            int oldlen = next_len;

            while (nx - next < oldlen) /* try to split at a space char */
            {
                nxp = nx;
                nx++;
                if (*nxp != ' ' && *nx != '\0') /* split on space or EOL */
                    continue;
                newlen = nxp - next;
                nw = font_getstringnsize(next, newlen, NULL, NULL, fontnum);

                if (nw > width)
                {
                    /* is next word larger than max width & room left on this line? */
                    if (nw - w > width && w + space_w * 8 < width)
                        w = nw;
                    break;
                }
                w = nw;
                next_len = newlen;
                store = nx; /* we want to skip the space char */
            }
            if (w > width) /* split when it fits */
            {
                w = width;
                next_len = font_measurestring(next, oldlen, w, &w, NULL, fontnum);
                store = next + next_len;
            }

            lines[line].len = next_len;
        }
        lastbreak = next + next_len;
    }

    /* prepare viewport
     * First boundaries, then the background filling, then the border and finally
     * the text*/

    screen->scroll_stop();

#ifdef PODTHINGS_MODERN_SPLASH
    maxw=MIN(MAX(maxw,216),vp->width-RECT_SPACING*2);
    maxh=MAX(maxh,44);
#endif
    width = maxw + 2*RECT_SPACING;
    height = maxh + 2*RECT_SPACING + SPLASH_TOP_DETAIL;

    if (width > vp->width)
        width = vp->width;
    if (height > vp->height)
        height = vp->height;

    /* center the vp in the screen area */
    vp->x += (vp->width - width) / 2;
    vp->y += (vp->height - height) / 2;
    vp->width = width;
    vp->height = height;
    if (!has_tabs)
        vp->flags |=  VP_FLAG_ALIGN_CENTER;

    /* prevent artifacts by locking to max width & height observed on repeated calls */
    max_width[screen->screen_type] = width - 2*RECT_SPACING;
    max_height[screen->screen_type] = height - 2*RECT_SPACING - SPLASH_TOP_DETAIL;

#ifdef PODTHINGS_MODERN_SPLASH
    if (screen->is_color)
        popup_card(screen,vp);
    else
#endif
    {
#if LCD_DEPTH > 1
    unsigned fg = 0, bg = 0;
    bool broken = false;

    if (screen->depth > 1)
    {
        fg = screen->get_foreground();
        bg = screen->get_background();

        if (fg == bg)
            broken = true;

#if defined(HAVE_LCD_COLOR)
        /* iPod reFresh themes from '22 */
        if (screen->is_color)
        {
            if (bg == SCREEN_COLOR_TO_NATIVE(screen, LCD_RGBPACK(244, 244, 244)) &&
                fg == SCREEN_COLOR_TO_NATIVE(screen, LCD_RGBPACK(255, 255, 255)))
                broken = true;
        }
#endif

        vp->drawmode = DRMODE_FG;
        /* can't do vp->fg_pattern here, since set_foreground does a bit more on
         * greyscale */
        screen->set_foreground(broken ? SCREEN_COLOR_TO_NATIVE(screen, LCD_LIGHTGRAY) :
                               bg);     /* gray as fallback for broken themes */
    }
    else
#endif
        vp->drawmode = (DRMODE_SOLID|DRMODE_INVERSEVID);

    screen->fill_viewport();

#if LCD_DEPTH > 1
    if (screen->depth > 1)
        /* can't do vp->fg_pattern here, since set_foreground does a bit more on
         * greyscale */
        screen->set_foreground(broken ? SCREEN_COLOR_TO_NATIVE(screen, LCD_BLACK) :
                               fg);     /* black as fallback for broken themes */
    else
#endif
        vp->drawmode = DRMODE_SOLID;

    screen->draw_border_viewport();
    }

    /* center y within the available splash box */
#ifdef PODTHINGS_MODERN_SPLASH
    y=RECT_SPACING+SPLASH_TOP_DETAIL+MAX(0,(maxh-y)/2);
#else
    if (y < maxh)
        y = (maxh - y) / 2;
    else
        y = RECT_SPACING;
#endif

    /* print the message to screen */
    for(int i = 0; i < line && y < height; i++, y+= chr_h)
    {
        if (lines[i].len > 0)
        {
            x = lines[i].x;
#ifdef PODTHINGS_MODERN_SPLASH
            if (has_tabs) x+=RECT_SPACING;
#endif
            screen->putsxyf(x, y, "%.*s", lines[i].len, lines[i].str);
        }
    }

    return true; /* needs update */
}

void splashf(int ticks, const char *fmt, ...)
{
    va_list ap;

    /* fmt may be a so called virtual pointer. See settings.h. */
    long id;
    if((id = P2ID((const unsigned char*)fmt)) >= 0)
        /* If fmt specifies a voicefont ID, and voice menus are
           enabled, then speak it. */
        cond_talk_ids_fq(id);

    /* If fmt is a lang ID then get the corresponding string (which
       still might contain % place holders). */
    fmt = P2STR((unsigned char *)fmt);
    FOR_NB_SCREENS(i)
    {
        struct screen * screen = &(screens[i]);
        struct viewport vp;
        viewport_set_defaults(&vp, screen->screen_type);
        struct viewport *last_vp = screen->set_viewport(&vp);

        va_start(ap, fmt);
        if (splash_internal(screen, fmt, ap, &vp, 0))
            screen->update_viewport();
        va_end(ap);

        screen->set_viewport(last_vp);
    }
    if (ticks)
        sleep(ticks);
}

/* set delay before progress meter is shown */
void splash_progress_set_delay(long delay_ticks)
{
    progress_next_tick = current_tick + delay_ticks;
    talked_tick = 0;
}

/* splash a progress meter */
void splash_progress(int current, int total, const char *fmt, ...)
{
    va_list ap;
    int vp_flag = VP_FLAG_VP_DIRTY;
    /* progress update tick */
    long now = current_tick;

    if (total<=0 || current < total)
    {
        if(TIME_BEFORE(now, progress_next_tick))
            return;
        /* limit to 20fps */
        progress_next_tick = now + HZ/20;
        vp_flag = 0; /* don't mark vp dirty to prevent flashing */
    }

    if (global_settings.talk_menu &&
        total > 0 &&
        TIME_AFTER(current_tick, talked_tick + HZ*5))
    {
        talked_tick = current_tick;
        talk_ids(false, LANG_LOADING_PERCENT,
                 TALK_ID(current * 100 / total, UNIT_PERCENT));
    }

    /* If fmt is a lang ID then get the corresponding string (which
       still might contain % place holders). */
    fmt = P2STR((unsigned char *)fmt);
    FOR_NB_SCREENS(i)
    {
        struct screen * screen = &(screens[i]);
        struct viewport vp;
        viewport_set_defaults(&vp, screen->screen_type);
        struct viewport *last_vp = screen->set_viewport_ex(&vp, vp_flag);

        va_start(ap, fmt);
        if (splash_internal(screen, fmt, ap, &vp, 1))
        {
            int size = screen->getcharheight();
            int x = RECT_SPACING;
            int y = vp.height - size - RECT_SPACING;
            int w = vp.width - RECT_SPACING * 2;
            int h = size;
#ifdef HAVE_LCD_COLOR
            const int sb_flags = HORIZONTAL | FOREGROUND;
#else
            const int sb_flags = HORIZONTAL;
#endif
#ifdef PODTHINGS_MODERN_SPLASH
            if (screen->is_color)
                popup_progress(screen,&vp,current,total);
            else
#endif
                gui_scrollbar_draw(screen, x, y, w, h, total, 0, current, sb_flags);

            screen->update_viewport();
        }
        va_end(ap);

        screen->set_viewport(last_vp);
    }
}
