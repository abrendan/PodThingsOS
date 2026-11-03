/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef PODTHINGS_SCRUB_H
#define PODTHINGS_SCRUB_H
#include <stdbool.h>
#include <stdint.h>
struct podthings_scrub {
    bool active, dirty;
    uint32_t target, length, last_input;
};
bool podthings_scrub_begin(struct podthings_scrub *, uint32_t position,
                          uint32_t length, uint32_t now);
void podthings_scrub_move(struct podthings_scrub *, int direction,
                         uint32_t step, uint32_t now);
bool podthings_scrub_finish(struct podthings_scrub *, bool accept, uint32_t *seek);
bool podthings_scrub_tick(struct podthings_scrub *, uint32_t now,
                         uint32_t settle, uint32_t timeout, uint32_t *seek);
void podthings_scrub_follow(struct podthings_scrub *, uint32_t position);
#endif
