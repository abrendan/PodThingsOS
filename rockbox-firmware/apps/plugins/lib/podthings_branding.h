/* Product labels only; keep upstream attribution and protocol identifiers. */
#ifndef PODTHINGS_BRANDING_H
#define PODTHINGS_BRANDING_H
#include "config.h"
#ifdef PODTHINGS_OS
#define PT_OS_NAME "PodThings OS"
#define PT_CLIENT_NAME "PodThingsOS"
#define PT_PRIVATE_DIR ".podthingsloader"
#else
#define PT_OS_NAME "Rockbox"
#define PT_CLIENT_NAME "Rockbox"
#define PT_PRIVATE_DIR ".rockbox"
#endif
#endif
