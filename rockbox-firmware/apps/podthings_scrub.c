/* SPDX-License-Identifier: GPL-2.0-or-later */
/* UI-thread state only. Native audio state/track identity stay in the WPS. */
#include "podthings_scrub.h"
#include <limits.h>

bool podthings_scrub_begin(struct podthings_scrub *s, uint32_t position,
                          uint32_t length, uint32_t now)
{
    *s=(struct podthings_scrub){0};
    if (!length || length>INT32_MAX) return false;
    s->active=true; s->length=length;
    s->target=position<length ? position : length-1;
    s->last_input=now;
    return true;
}
void podthings_scrub_move(struct podthings_scrub *s, int direction,
                         uint32_t step, uint32_t now)
{
    if (!s->active || !direction) return;
    uint32_t last=s->target;
    if (direction>0)
        s->target=step>=s->length-1-s->target ? s->length-1 : s->target+step;
    else
        s->target=step>=s->target ? 0 : s->target-step;
    s->dirty=s->dirty || s->target!=last;
    s->last_input=now;
}
bool podthings_scrub_finish(struct podthings_scrub *s, bool accept, uint32_t *seek)
{
    bool commit=s->active && s->dirty && accept;
    if (commit) *seek=s->target;
    s->active=s->dirty=false;
    return commit;
}
bool podthings_scrub_tick(struct podthings_scrub *s, uint32_t now,
                         uint32_t settle, uint32_t timeout, uint32_t *seek)
{
    if (!s->active) return false;
    uint32_t idle=now-s->last_input; /* defined across tick wrap */
    if (idle>=timeout) return podthings_scrub_finish(s,true,seek);
    if (s->dirty && idle>=settle) {
        *seek=s->target; s->dirty=false; return true;
    }
    return false;
}
void podthings_scrub_follow(struct podthings_scrub *s, uint32_t position)
{
    if (s->active && !s->dirty)
        s->target=position<s->length ? position : s->length-1;
}
